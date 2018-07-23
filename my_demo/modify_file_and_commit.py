# encoding:utf-8
import pymongo
import re
from functools import reduce
import requests
import time
from bs4 import BeautifulSoup
from my_demo import utils
from selenium.webdriver.common.keys import Keys
from selenium.common import exceptions
import git
import os


file_path = 'E:/git-repository/blog/ccw33.github.io/file/http_surge.pac'
file_path_chrome = 'E:/git-repository/blog/ccw33.github.io/file/OmegaProfile_auto_switch.pac'
git_repo_path =  'E:/git-repository/blog/ccw33.github.io'

def generate_replace_text(ip_fanqiang_list):
    new_proxy_list = ["%s%s = %s,%s\n" % (ip['proxy_type'],str(index),ip['proxy_type'] if ip['proxy_type']=='http' else 'socks5',ip['ip_with_port'].replace(':',',')) for index,ip in enumerate(ip_fanqiang_list)]
    new_proxy_group = [s.split('=')[0] for s in new_proxy_list]
    return (reduce(lambda v1,v2:v1+v2,new_proxy_list),reduce(lambda v1,v2:v1+','+v2,new_proxy_group)+',')

# 修改pac文件并commit到github
def update_pac_and_push():
    '''
    更新surge用的pac
    :return:
    '''
    client = pymongo.MongoClient('localhost', 27017)
    ips = client['ips']
    ipsFanqiangData = ips['ipsFanqiangData']
    if not list(ipsFanqiangData.find())[-1]['ip_fanqiang_list']:
        return
    ip_fanqiang_list = list(ipsFanqiangData.find())[-1]['ip_fanqiang_list']
    client.close()

    #获取repo
    repo = git.Repo(path=git_repo_path)

    # 读取文件
    old_text = ''
    new_text = ''
    with open(file_path, 'r', encoding='utf-8') as fr:
        old_text = fr.read()
        proxy_replace_text ,group_replace_text = generate_replace_text(ip_fanqiang_list)
        new_text = old_text.replace(re.findall(r'\[Proxy\]\n((?:.+\n)+)Socks1',
                                               old_text)[0], proxy_replace_text)
        new_text = new_text.replace(re.findall(r'\[Proxy Group\]\nProxy = url-test, (.+) url = http://www.google.com/generate_204\nSocks_Proxy',
                                               new_text)[0], group_replace_text)

    #修改文件
    with open(file_path, 'w',encoding='utf-8') as fw:
        fw.write(new_text)

    #git commit

    #commit
    repo.index.add([file_path.replace(git_repo_path+'/','')])
    repo.index.commit('auto update '+ file_path)
    #获取远程库origin
    remote = repo.remote()
    #提交到远程库
    remote.push()

def update_chrome_pac():
    '''
    更新chrome用的pac
    :return:
    '''
    # 初始化数据库
    client = pymongo.MongoClient('localhost', 27017)
    ips = client['ips']
    ipsData = ips['ipsData']
    ipsFanqiangData = ips['ipsFanqiangData']

    old_data = list(ipsFanqiangData.find())[-1]
    ip_fanqiang_list = old_data['ip_fanqiang_list']
    ip_fanqiang_list = sorted(ip_fanqiang_list, key=lambda ip: ip['time'])

    # 把需要验证的去掉
    proxy_type = 'socks5'
    ok_list = []
    for ip_dict in ip_fanqiang_list:
        driver=None
        try:
            ip_with_port = ip_dict['ip_with_port']
            resp = requests.get('http://www.google.com/', headers=utils.headers,
                                proxies={'http': proxy_type + (
                                    'h' if proxy_type == 'socks5' else '') + '://' + ip_with_port,
                                         'https': proxy_type + (
                                             'h' if proxy_type == 'socks5' else '') + '://' + ip_with_port},
                                timeout=10)
            soup = BeautifulSoup(resp.text, 'lxml')
            driver = utils.ready(ip_dict)
            driver.set_page_load_timeout(60)
            driver.get('http://www.google.com/')
            tags = utils.wait_and_get_elements_until_ok(driver, '#lst-ib')
            tags[0].send_keys('kkk')
            tags[0].send_keys(Keys.ENTER)
            if re.findall('我们的系统检测到您的计算机网络中存在异常流量', driver.page_source):  # 证明需要机器人验证
                driver.quit() #TODO 删除该ip_port
                continue
            else:  # 不需要验证，可以使用
                # 替换ip和port
                new_text = ''
                with open(file_path_chrome,
                          'r', encoding='utf-8') as fr:
                    old_text = fr.read()
                    new_text = old_text.replace(re.findall(r'(?:SOCKS |SOCKS5 )(\d+\.\d+\.\d+\.\d+:\d+)', old_text)[0],
                                                ip_with_port)
                    new_text = new_text.replace(re.findall(r'(?:SOCKS |SOCKS5 )(\d+\.\d+\.\d+\.\d+:\d+)', old_text)[1],
                                                ip_with_port)
                with open(file_path_chrome,
                          'w', encoding='utf-8') as fw:
                    fw.write(new_text)
                # 获取repo
                repo = git.Repo(path=git_repo_path)
                # commit
                repo.index.add([file_path.replace(git_repo_path + '/', '')])
                repo.index.commit('auto update ' + file_path)
                # 获取远程库origin
                remote = repo.remote()
                # 提交到远程库
                remote.push()
                break
        except exceptions.TimeoutException as e: # 浏览器访问超时
            driver.quit()
            ip_fanqiang_list.remove(ip_dict)
            continue
        except requests.ConnectionError as e: # request 访问错误
            ip_fanqiang_list.remove(ip_dict)
            continue
        except requests.ReadTimeout as e: #request 超时
            ip_fanqiang_list.remove(ip_dict)
            continue
        except Exception as e:
            if driver:
                driver.quit()
            if re.findall(r'NoneType',str(e)):
                continue
            continue

    #测试proxy文件里面的
    ip_fanqiang_list = update_chrome_pac_by_gatherproxy(ip_fanqiang_list)

    # 更新数据库
    ipsFanqiangData.update_one({'_id': old_data['_id']}, {'$set': {
        'updated_at': time.strftime('%Y-%m-%d'),
        'ip_fanqiang_list': ip_fanqiang_list,
        'isFanqiang': True
    }}, upsert=True)
    client.close()

def update_chrome_pac_by_gatherproxy(ip_fanqiang_list):
    '''
    更新chrome用的pac
    :return:
    '''
    try:
        with open('file/proxies.txt','r') as fr:
            ip_port_list = fr.read().split('\n')
    except Exception:
        return ip_fanqiang_list

    # 把需要验证的去掉
    proxy_type = 'socks5'
    is_ok_at_least_one = False
    for ip_with_port in ip_port_list:
        ip_dict = {
            'ip_with_port':ip_with_port,
            'proxy_type':'socks5'
        }
        driver=None
        try:
            resp = requests.get('http://www.google.com/', headers=utils.headers,
                                proxies={'http': proxy_type + (
                                    'h' if proxy_type == 'socks5' else '') + '://' + ip_with_port,
                                         'https': proxy_type + (
                                             'h' if proxy_type == 'socks5' else '') + '://' + ip_with_port},
                                timeout=10)
            soup = BeautifulSoup(resp.text, 'lxml')
            driver = utils.ready(ip_dict)
            driver.set_page_load_timeout(60)
            driver.get('http://www.google.com/')
            tags = utils.wait_and_get_elements_until_ok(driver, '#lst-ib')
            tags[0].send_keys('kkk')
            tags[0].send_keys(Keys.ENTER)
            if re.findall('我们的系统检测到您的计算机网络中存在异常流量', driver.page_source):  # 证明需要机器人验证
                driver.quit()
                continue
            else:  # 不需要验证，可以使用
                # 添加到数据库
                result_list = utils.get_useful_ip(ip_with_port,'socks5',None,[])[1]
                if result_list:
                    ip_fanqiang_list.append(result_list[0])
                if is_ok_at_least_one:#如果已经有成功的，直接继续，无需修改
                    continue
                # 替换ip和port
                new_text = ''
                with open(file_path_chrome,
                          'r', encoding='utf-8') as fr:
                    old_text = fr.read()
                    new_text = old_text.replace(re.findall(r'(?:SOCKS |SOCKS5 )(\d+\.\d+\.\d+\.\d+:\d+)', old_text)[0],
                                                ip_with_port)
                    new_text = new_text.replace(re.findall(r'(?:SOCKS |SOCKS5 )(\d+\.\d+\.\d+\.\d+:\d+)', old_text)[1],
                                                ip_with_port)
                with open(file_path_chrome,
                          'w', encoding='utf-8') as fw:
                    fw.write(new_text)
                # 获取repo
                repo = git.Repo(path=git_repo_path)
                # commit
                repo.index.add([file_path.replace(git_repo_path + '/', '')])
                repo.index.commit('auto update ' + file_path)
                # 获取远程库origin
                remote = repo.remote()
                # 提交到远程库
                remote.push()
                is_ok_at_least_one=True
                continue
        except exceptions.TimeoutException as e: # 浏览器访问超时
            driver.quit()
            continue
        except requests.ConnectionError as e: # request 访问错误
            continue
        except requests.ReadTimeout as e: #request 超时
            continue
        except Exception as e:
            if driver:
                driver.quit()
            if re.findall(r'NoneType',str(e)):
                continue
            continue
    #跑完，吧proxy文件删了
    os.remove('file/proxies.txt')
    return ip_fanqiang_list


if __name__ == "__main__":
    # update_pac_and_push()
    update_chrome_pac()