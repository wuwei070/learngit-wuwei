# -*- coding: utf-8 -*-

#思路图--》代码分块，最好能写个伪码，然后根据伪码写

'''
一个文件里面有很多ip，但同一个段的ip有很多，我只需要取出一个就好，这样能吧ip缩减
'''
from sys import argv
import re

ip_file = argv[1]

#用来存储每个ip的前三位为key， 整个ip为值
dic = {}

f = open(ip_file)


#每读取一行，把ip的前三位去出来当成key， ip当value， 这样做是为了同一个段的ip取出一个就好了
for line in f:
    pattern = re.compile('\d{1,3}\\.\d{1,3}\\.\d{1,3}\\.')
    key = pattern.findall(line.strip().replace('\n', ''))[0]
    ip = line.strip().replace('\n', '')
    if dic.has_key(key):
        continue
    else:
        dic[key] = ip
    
f.close()

for value in dic.values():
    print value