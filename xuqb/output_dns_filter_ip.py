#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2017-08-01 23:17:02
# @Author  : wuwei
# @Link    : 
# @Version : v1.0

'''

1. wireshark里面dns过滤出来的域名的ip，整理成1行，方便写入配置文件
2.整理成域名 ip对应的形式
'''

import sys
import fileinput
import re

dns_filter_file = sys.argv[1]
IP_list = []

def getip(line):
    iplist = []
    pattern = re.compile('A \d{1,3}\\.\d{1,3}\\.\d{1,3}\\.\d{1,3}')
    ip_string_list = pattern.findall(line)
    for i in ip_string_list:
        ip = i.split()[1]
        if ip == '127.0.0.1': continue
        iplist.append(ip)
    return iplist
        
for line in fileinput.input(dns_filter_file):
    IP_list += getip(line)
    
IP_list = list(set(IP_list))
print ' '.join(IP_list)
