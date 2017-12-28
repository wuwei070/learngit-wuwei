#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2017-07-14 12:48
# @Author  : wuwei
# @Link    : 
# @Version : v1.0

'''
背景：排查发现和局方内网互联质量差，局方流量是从不同设备过来的，ip地址段不一样，现到squid捞日志获取用户ip，然后判断哪些段的ip质量差，好定位是哪个地区出了问题
思路：根据输入的内网ip列表，调用操作系统的ping命令，批量同时ping ip列表，根据输出来判断网络质量的好坏，把质量差的ip打印出来
'''


import re
import subprocess
import threading

class Ping(threading.Thread):

    def __init__(self,ip):
        super(Ping,self).__init__()
        self.ip = ip

    def run(self):
        count = 5
        timeout = 1
        cmd = 'ping -c %d -w %d %s'%(count,timeout,self.ip)
        p = subprocess.Popen(cmd,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=True
        )
 
        ping_result=p.stdout.read()
        last_line = ping_result.split('\n')[-2]
        pat = re.compile(r'rtt min/avg/max/mdev = \d+(?:\.\d+)?/(\d+(?:\.\d+)?)/\d+(?:\.\d+)?/\d+(?:\.\d+)? ms')
        try:
            avg = int(float(pat.findall(last_line)[0]))
        except IndexError:
            return None
        if avg > 5:
            self.result = self.ip
        else:
            self.result = None
        

    def get_result(self):
        try:
            return self.result  # 如果子线程不使用join方法，此处可能会报没有self.result的错误
        except Exception:
            return None
		 
if __name__ == "__main__":
    threads = []
    poor_quality_ip = []
    f = open('hostip.txt','r')
    for line in f.readlines():
        ip = line.strip()
        t = Ping(ip)
        threads.append(t)
        t.start()
    f.close()
    for i in threads:
        i.join()
        ip = i.get_result()
        if ip:
            poor_quality_ip.append(ip)
   
    for j in poor_quality_ip:
        print j