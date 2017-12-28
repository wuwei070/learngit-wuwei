#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2017-08-01 23:17:02
# @Author  : wuwei
# @Link    : 
# @Version : v1.0

'''
根据别人提供的文件，把这个文件里面的每一行url并发下载下来，并保存到特定的目录
'''

import os
import urllib
import threading
import logging
from multiprocessing import  Pool
import socket

logging.basicConfig(level=logging.DEBUG,
                format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                datefmt='%a, %d %b %Y %H:%M:%S',
                filename='fail.log',
                filemode='w')

download_dir = os.path.join('d:\\', 'download')
if not os.path.exists(download_dir):
    print "mkdir %s " % download_dir
    os.mkdir(download_dir)
	
def download_url(url, i):
   # url_filename = url[url.rfind('/')+1:]
    url_filename = '.'.join((i, 'mp4'))
    local_filepath = os.path.join(download_dir, url_filename)
    if not os.path.isfile(local_filepath):
        print "download %s" % url_filename
        try:
            urllib.urlretrieve(url, local_filepath)
        except socket.timeout:
            logging.warning('download %s timeout' % url)
        except Exception, e:
            logging.warning("download %s fail" % url)
    else:
        logging.warning("%s repeat download!" % url)
		
if __name__ == "__main__":
    p = Pool(20)
    j = 0
    f = open(r'C:\Users\xuqb\Desktop\xuqb\urls.txt','r')
    for line in f:
        j += 1
        
        url = line.strip()
        #download_url(url, str(j))
        p.apply_async(download_url, args=(url,str(j)))   #维持执行的进程总数为processes，当一个进程执行完毕后会添加新的进程进去
    p.close() #调用join之前，先调用close函数，否则会出错。执行完close后不会有新的进程加入到pool,join函数等待所有子进程结束
    p.join()
    f.close()
        