#coding:utf-8

import requests
headers = {

    "User-Agent":"Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.186 Safari/537.36"
}
response =requests.get("http://www.zhihu.com",headers=headers)

print(response.text)