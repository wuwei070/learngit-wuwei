#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2017-07-14 12:48
# @Author  : wuwei
# @Link    : 
# @Version : v1.0

'''
思路：从2个文件，分别获取ip和路由，组成ip列表和路由列表，同时把IP列表和路由列表分别拆分成A类，B类，C类。然后A类ip列表和A类路由列表对比，
B类ip列表和B类路由列表对比， C类ip列表和C类路由列表对比,对比的结果分别存入repeat_list和no_repeat_list

'''

from sys import argv
from check_ip_in_net import *
import ConfigParser
import re
import os

cf_file = argv[1]

content = open(cf_file).read()  
#Window下用记事本打开配置文件并修改保存后，编码为UNICODE或UTF-8的文件的文件头  
#会被相应的加上\xff\xfe（\xff\xfe）或\xef\xbb\xbf，然后再传递给ConfigParser解析的时候会出错  
#，因此解析之前，先替换掉  
content = re.sub(r"\xfe\xff","", content)  
content = re.sub(r"\xff\xfe","", content)  
content = re.sub(r"\xef\xbb\xbf","", content)  
open(cf_file, 'w').write(content)

#每次运行脚本之前都把旧的结果删除
repeat_f = os.path.join(os.getcwd(), 'repeat.txt')
norepeat_f = os.path.join(os.getcwd(), 'norepeat.txt')
if os.path.exists(repeat_f):
    os.remove(repeat_f)
if os.path.exists(norepeat_f):
    os.remove(norepeat_f)

#获取ops_file里面的ip组成一个列表
def get_ops_ip(f, ip_column):
    tmp_ops_iplist = ops_iplist[:]
    count = 1
    for line in f:
        if count == 1:  #忽略第1行
            count += 1
            continue
        try:
            ip = line.split()[ip_column].strip()
            tmp_ops_iplist.append(ip)
        except IndexError, TypeError:
		#字符串在Python内部的表示是unicode编码，因此，在做编码转换时，通常需要以unicode作为中间编码，即先将其他编码的字符串解码（decode）成unicode，再从unicode编码（encode）成另一种编码。
        #decode的作用是将其他编码的字符串转换成unicode编码，如str1.decode('gb2312')，表示将gb2312编码的字符串转换成unicode编码。
        #encode的作用是将unicode编码转换成其他编码的字符串，如str2.encode('gb2312')，表示将unicode编码的字符串转换成gb2312编码。
        #在某些IDE中，字符串的输出总是出现乱码，甚至错误，其实是由于IDE的结果输出控制台自身不能显示字符串的编码，而不是程序本身的问题。
            print line.decode('gbk').encode('gbk')  #因为ops文件的默认保存格式是utf-8的
    tmp_ops_iplist = list(set(tmp_ops_iplist))
    return tmp_ops_iplist[:]


#获取allgame_file里面的路由组成一个列表
def get_allgame_route(f, route_column):
    tmp_allgame_routelist = allgame_routelist[:]
    count = 1 
    for line in f:
        if count == 1:  #忽略第1行
            count += 1
            continue
        try:
            route = line.split()[route_column].strip()
            tmp_allgame_routelist.append(route)
        except IndexError, TypeError:
            print line.decode('utf8').encode('gbk')
    tmp_allgame_routelist = list(set(tmp_allgame_routelist))
    return tmp_allgame_routelist[:]
	
#判断一个ip或者网段属于A类:1~126，B类:128~192，C类:193~224
def check_ip_subnet_in_abc(subnet):
    first_segment = int(subnet.split('.')[0])
    if 1 < first_segment < 126:
        return 'A'
    elif 128 < first_segment < 192:
        return 'B'
    elif 193 < first_segment < 224:
        return 'C'

#根据别人提供的ip或路由列表分成A, B, C 三类		
def separate_subnet_to_ABC(iplist):
    iplist_A = []
    iplist_B = []
    iplist_C = []
    for ip in iplist:
        if 'A' == check_ip_subnet_in_abc(ip):
            iplist_A.append(ip)
        elif 'B' == check_ip_subnet_in_abc(ip):
            iplist_B.append(ip)
        elif 'C' == check_ip_subnet_in_abc(ip):
            iplist_C.append(ip)
    return iplist_A[:], iplist_B[:], iplist_C[:]

#根据别人提供的重复ip列表和不重复ip列表，把文件拆分成2部分	
def separate_repeat_and_norepeat_ip(f_r, f_repeat_w, f_norepeat_w, ip_column):
    count = 1
    for line in f_r:
        try:
            ip = line.split()[ip_column].strip()
        except IndexError, TypeError:
            print line.decode('utf8').encode('gbk')
            continue
        if count == 1:
            f_repeat_w.write(line)
            f_norepeat_w.write(line)
            count += 1
        else:
            if ip in repeat_list:
                f_repeat_w.write(line)
            else:
                f_norepeat_w.write(line)
                    				
        		
	
if __name__ == "__main__":
    
    ops_iplist = []
    ops_iplist_A = []
    ops_iplist_B = []
    ops_iplist_C = []

    allgame_routelist = []
    allgame_routelist_A = []
    allgame_routelist_B = []
    allgame_routelist_C = []

    repeat_list = []
    no_repeat_list = []
	
    #获取ops.txt文件路径和allgame.txt文件路径以及它们对比的列
    cf = ConfigParser.ConfigParser()
    cf.read(cf_file)
    ops_file = cf.get("IpContrast", "OperationFileName")
    ops_column = int(cf.get("IpContrast", "OperationFileColumn")) - 1
    allgame_file = cf.get("IpContrast", "ReferenceFileName")
    allgame_column = int(cf.get("IpContrast", "ReferenceFileColumn")) - 1
    
	
	#获取分成A, B, C类的ip列表
    f_ops = open(ops_file, 'r')
    ops_iplist = get_ops_ip(f_ops, ops_column)
    ops_iplist_A, ops_iplist_B, ops_iplist_C = separate_subnet_to_ABC(ops_iplist)
    f_ops.close()

	#获取分成A, B, C类的路由列表
    f_allgame = open(allgame_file, 'r')
    allgame_routelist = get_allgame_route(f_allgame, allgame_column)
    allgame_routelist_A, allgame_routelist_B, allgame_routelist_C = separate_subnet_to_ABC(allgame_routelist)
    f_allgame.close()
	
	#拆分重复和不重复的ip
    for ip_A in ops_iplist_A:
        for subnet_A in allgame_routelist_A:
            if ip_in_subnet(ip_A,subnet_A):
                repeat_list.append(ip_A)
                break
        else:
            no_repeat_list.append(ip_A)
			
    for ip_B in ops_iplist_B:
        for subnet_B in allgame_routelist_B:
            if ip_in_subnet(ip_B,subnet_B):
                repeat_list.append(ip_B)
                break
        else:
            no_repeat_list.append(ip_B)
			
    for ip_C in ops_iplist_C:
        for subnet_C in allgame_routelist_C:
            if ip_in_subnet(ip_C,subnet_C):
                repeat_list.append(ip_C)
                break
        else:
            no_repeat_list.append(ip_C)
	#分离ops文件，输出repeat.txt和norepeat.txt		
    f_ops = open(ops_file, 'r')
    f_repeat_file = open(os.path.join(os.getcwd(), 'repeat.txt'), 'a+')
    f_norepeat_file = open(os.path.join(os.getcwd(), 'norepeat.txt'), 'a+')
    separate_repeat_and_norepeat_ip(f_ops, f_repeat_file, f_norepeat_file, ops_column)
    f_ops.close()
    f_repeat_file.close()	
    f_norepeat_file.close()
	
	
	


    
            		
