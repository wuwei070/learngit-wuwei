# -*- coding: utf-8 -*-
#Counter 类
#思路图--》代码分块，最好能写个伪码，然后根据伪码写
from sys import argv

squid_file = argv[1]

#用来存储每个ip和对应的ip访问次数
dic = {}

f = open(squid_file)

#每读取一行, 把第一个字段截取出来，如果第一个字段的这个ip在字典里面存在，就递增1，不存在就赋值为1
for line in f:
    ip = line.split()[0]
    if dic.has_key(ip):
        dic[ip] += 1
    else:
        dic[ip] = 1
    
f.close()

#循环读取字典，把每个ip和对应的ip访问次数打印出来
for key,value in dic.items():
    print "%s: %s" % (key,value)