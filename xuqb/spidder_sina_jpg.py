#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2017-08-21 11:29:02
# @Author  : wuwei
# @Link    : 
# @Version : v1.0

'''
爬取新浪网站的图片
'''

import os
import urllib
import urllib2
import threading
import logging
from multiprocessing import  Pool
import socket
from bs4 import BeautifulSoup 
import re

logging.basicConfig(level=logging.DEBUG,
                format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                datefmt='%a, %d %b %Y %H:%M:%S',
                filename='fail.log',
                filemode='w')

download_dir = os.path.join('d:\\', 'download')
if not os.path.exists(download_dir):
    print "mkdir %s " % download_dir
    os.mkdir(download_dir)
	
	
class Spidder_sina():
    def __init__(self, url, max=3):
        self.url = url
        self.html = ''
        self.links = []
        self.pic_links = []
		
    def get_html(self):
        user_agent = "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; AcooBrowser; .NET CLR 1.1.4322; .NET CLR 2.0.50727)"
        headers = { 'User-Agent' : user_agent }
        req_body = ''
        req = urllib2.Request(self.url)
        req.add_header('User-Agent', user_agent)	
        response = urllib2.urlopen(req)  
        self.html = response.read()
		
    def get_all_links(self):
        soup = BeautifulSoup(self.html)
        for tag in soup.find_all(True):
            link1 = tag.get('href')
            link2 = tag.get('src')
            if link1:
                self.links.append(link1)
            if link2:
                self.links.append(link2)
        return self.links
		
    def get_pic_links(self):
        #图片格式是计算机存储图片的格式，常见的存储的格式有bmp,jpg,png,tiff,gif,pcx,tga,exif,fpx,svg,psd,cdr,pcd,dxf,ufo,eps,ai,raw,WMF等
        format_of_pic = ['bmp', 'jpg', 'png', 'tiff', 'gif', 'pcx', 'tga', 'exif', 'fpx', 'svg', 'psd', 'cdr', 'pcd', 'dxf', 'ufo', 'eps', 'ai', 'raw', 'WMF']
        for link in self.links:
            if link[link.rfind('.')+1:] in format_of_pic:
                if re.search('^//', link):
                    link = 'http:' + link
                self.pic_links.append(link)
        return self.pic_links 
    def 
        
	
def download_url(url):
    url_filename = url[url.rfind('/')+1:]
    local_filepath = os.path.join(download_dir, url_filename)
    if not os.path.isfile(local_filepath):
        print "download %s" % url
        try:
            urllib.urlretrieve(url, local_filepath)
        except socket.timeout:
            logging.warning('download %s timeout' % url)
        except Exception, e:
            logging.warning("download %s fail" % url)
    else:
        logging.warning("%s repeat download!" % url)
		
if __name__ == "__main__":
    c_sina = Spidder_sina('http://www.sina.com.cn')
    c_sina.get_html()
    c_sina.get_all_links()
    #c_sina.get_pic_links()
    p = Pool(20)
    j = 0
    for url in c_sina.get_pic_links():
        j += 1
        
        url = url.strip()
        download_url(url)
        p.apply_async(download_url, args=(url,))   #维持执行的进程总数为processes，当一个进程执行完毕后会添加新的进程进去
    p.close() #调用join之前，先调用close函数，否则会出错。执行完close后不会有新的进程加入到pool,join函数等待所有子进程结束
    p.join()
    
        