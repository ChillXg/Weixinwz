from pyquery import PyQuery as pq
from urllib.parse import urlencode
from requests import ConnectionError
import requests
from config import *
import pymongo
from lxml.etree import XMLSyntaxError

client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]


PROXY_POOL_URL = 'http://127.0.0.1:5555/random'
proxy = None
MAX_COUNT = 5

headers = {
'Cookie':'SUV=00DB0B5B7D5EC8FF595A6411D655B302; CXID=1113B5660F2BA435FC046EF8DB95AC2B; wuid=AAEaapxiGgAAAAqLE2MYZQAAGwY=; pgv_pvi=5598076928; ssuid=808455940; dt_ssuid=9443597135; GOTO=Af22417-3002; tv_play_records=%D6%D0%B9%FA%D3%D0%CE%FB%B9%FE:20170902; pex=C864C03270DED3DD8A06887A372DA219231FFAC25A9D64AE09E82AED12E416AC; usid=J6qE4JHQiC-dNYB_; UM_distinctid=160cc38ced929d-0124df8f41793f-6037716d-100200-160cc38cedb395; ad=$Zllllllll2zXfChlllllVrmiH9lllllKqEwjlllll9lllllxOxlw@@@@@@@@@@@; SUID=7DC85E7D3965860A595CDCE200050A36; ABTEST=0|1526618554|v1; IPLOC=CN4401; JSESSIONID=aaaFX75N-p2eb-BLghjnw; weixinIndexVisited=1; PHPSESSID=0j4nthih50si7mmhal1oisjpk2; SUIR=44E36D4E33375F41A486E25833083A43; SNUID=71D6597A08026B7F214DECEC085A0907; sct=144; ppinf=5|1526639169|1527848769|dHJ1c3Q6MToxfGNsaWVudGlkOjQ6MjAxN3x1bmlxbmFtZToyNzolRTUlQkUlOTAlRTUlQjklQkYlRTklOTIlOEF8Y3J0OjEwOjE1MjY2MzkxNjl8cmVmbmljazoyNzolRTUlQkUlOTAlRTUlQjklQkYlRTklOTIlOEF8dXNlcmlkOjQ0Om85dDJsdUZ1UV9ocVF3QU9odjRCM3dET19Wa29Ad2VpeGluLnNvaHUuY29tfA; pprdig=eOwDj_bhcy3UcHEOF9CYOpEd7gK80BW1phVUu2SC5jGEiGJagclF8iCvtQ6ObMM72cWlIzZ9BA0YDIHVh1wMJjg_gaIVVOr60i7x_s3-8l45buRZUZxgEewZKqAXI5bA4AsufhDmaN5Q5SIbS-KGFIuOOJn1OURdNHIhkn49Sb4; sgid=07-32977203-AVribqkGGWKEYFaefvaVy7MM; ppmdig=15266391690000008e818ad69639a4a9a390dab95e610b55',
'Host':'weixin.sogou.com',
'Upgrade-Insecure-Requests':'1',
'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Maxthon/5.1.2.3000 Chrome/55.0.2883.75 Safari/537.36'
}

def get_proxy():#获取代理IP池里的IP，需要定期寻找新的IP网站
    try:
        response = requests.get(PROXY_POOL_URL)
        if response.status_code == 200:
            print(response.status_code)
            return response.text
        else:
            print('请求ip失败')
            return None
    except ConnectionError:
        print('请求ip失败')
        return None



def get_html(url, count=1):#爬取IP池IP地址
    print('正在抓的url', url)
    print('当前请求次数', count)
    global proxy
    if count >= MAX_COUNT:
        print('请求次数太多了')
        return None
    try:
        if proxy:
            proxies = {
                'http': 'http://' + proxy
            }
            response = requests.get(url, allow_redirects=False, headers=headers, proxies=proxies)
        else:
            response = requests.get(url, allow_redirects=False, headers=headers)
        if response.status_code == 200:
            return response.text
        if response.status_code == 302:
            #需要代理IP
            print('302')
            proxy = get_proxy()
            if proxy:
                print('正用代理', proxy)
                return get_html(url)
            else:
                return None
    except ConnectionError as e:
        print('请求网页失败,重试次数', e.args)
        proxy = get_proxy()
        count += 1
        return get_html(url, count)

def get_one_page_index(keywords, page):
    data = {
        'query': keywords,
        'type': '2',
        'page': page
    }
    url = 'http://weixin.sogou.com/weixin?' + urlencode(data)
    html = get_html(url)
    return html

def parse_index(html):#索引拿到的数据，
    doc = pq(html)
    items = doc('.news-box .news-list li .txt-box h3 a').items()
    for item in items:
        yield item.attr('href')

def get_detail(url):#模拟点击后的url网站
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        return None
    except ConnectionError:
        return None


def parse_detail(html):
    try:
        doc = pq(html)
        title = doc('.rich_media_title').text()#要的是它的类
        content = doc('.rich_media_content').text()
        date = doc('.rich_media_meta rich_media_meta_text').text()
        nickname = doc('#js_profile_qrcode > div > strong').text()
        wechat = doc('#js_profile_qrcode > div > p:nth-child(3) > span').text()
        return {
            'title': title,
            'content': content,
            'date': date,
            'nickname': nickname,
            'wechat': wechat
        }
    except XMLSyntaxError:
        return None

def save_to_mongo(data):
    if db['articles'].update({'title': data['title']}, {'$set': data}, True):
        print('Saved to Mongo', data['title'])
    else:
        print('Saved to Mongo Failed', data['title'])




def main():
    for page in range(1, 101):
        html = get_one_page_index(keywords, page)
        if html:
            article_urls = parse_index(html)
            for article_url in article_urls:
                article_html = get_detail(article_url)
                if article_html:
                    article_data = parse_detail(article_html)
                    print(article_data)
                    if article_data:
                        save_to_mongo(article_data)




if __name__ == '__main__':
    main()