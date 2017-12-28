#! /usr/bin/env python
# -*- coding: utf-8 -*-

'''
监控逻辑：  1.检查/var/log/messages里面的日志信息看是否磁盘有啥故障
            2.运行smartctl -A 来检查获取磁盘信息，并且根据里面的阀值来判断磁盘是否异常
			3.把检查结果存入zbx_sender_scandisk.conf 这个文件里面，同时发送给zabbix做监控

'''




import argparse
import logging
import subprocess
import re
import time
import os
import logging.handlers
from datetime import datetime
from datetime import date

####定义一个log类 ####
class LOG(object):
  def __init__(self,path,level,mxsize,bkcount):
    self.Log = logging.getLogger(path)  #返回一个logger对象，如果没有指定名字将返回root logger
    self.Log.setLevel(level)
    rhandler = logging.handlers.RotatingFileHandler(
        filename=path,maxBytes=mxsize,backupCount=bkcount)
    sfmt = "%(asctime)-15s[%(levelname)s] %(filename)s:[%(lineno)d] %(message)s"
    cfmt = logging.Formatter(fmt=sfmt)
    rhandler.setFormatter(cfmt)
    rhandler.setLevel(level)
    pass 
    self.Log.addHandler(rhandler)

  def GetLog(self):
    return self.Log
  def debug(self, msg):
    self.Log.debug(msg)
  def info(self, msg):
    self.Log.info(msg)
  def error(self,msg):
    self.Log.error(msg)
  def warn(self,msg):
    self.Log.warn(msg)
#####

class TimeElapse:
  def __init__(self, log, func_name="test"):
    self.b_time = time.time() 
    self.func_name = func_name
    self.log = log

  def __del__(self):   # 计算扫描花了多少时间
    e_time = time.time() 
    b_dt = datetime.fromtimestamp(self.b_time) 
    e_dt = datetime.fromtimestamp(e_time) 
    diff_tm = e_dt.minute* 60 + e_dt.hour*3600 + e_dt.second + \
        e_dt.microsecond/1000- ( 
        b_dt.second + b_dt.microsecond/1000 + 
        b_dt.minute*60 + b_dt.hour*3600)
    self.log.info(" %s elapse tm: %d ms" % 
        (self.func_name, diff_tm))
    pass

class  CmdParse:
  def __init__(self):
    self.log_file = None
    self.report_data_path = None
    self.host = None
    self.log_bak_nums = 4
    self.log_max_size_bytes = 5*1024*1024
    self.log_level = logging.DEBUG 
    self.scan_sys_log_inter_tm = 1 #unit is hour,scan log >= now.hour -3
    ##
  def ParseCmd(self):
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--zbx_conf',dest='zbx_conf',
        type=str,default='/etc/zabbix/zabbix_agentd.conf')
    parser.add_argument('--host', dest='host',
        type=str, default='localhost')
    parser.add_argument('--port',dest='port',type=int, required=True)
    parser.add_argument('--scan_data_path',dest='scan_data_path',
        type=str,default='/op')
    parser.add_argument('--log_file',dest='log_file',
        type=str,default='/opt/zbx_scan_disk.log')
    parser.add_argument('--test_type',dest='test_type',
        type=str,required=True,choices=['timing_run','io_cond_run'],
        help='scan disk conditions')
    parser.add_argument('--data_path',dest='data_path',
        type = str, help = 'store scan disk info data\'s path',
        default = '/opt/') 
    parser.add_argument('--ip', dest='ip', 
        type =str, help = 'ip', required = True)
    parser.add_argument('--scan_inter_h',dest='scan_inter_h', type =int,
        default=3,help='scan sys log inter hours')
    args = parser.parse_args();
    pass
    self.log_file = args.log_file
    self.report_data_path = args.scan_data_path
    self.host = args.host
    self.port = args.port
    self.ip = args.ip
    self.zbx_conf = args.zbx_conf
    self.test_type = args.test_type 
    self.store_scan_diskdat_path = args.data_path
    self.scan_sys_log_inter_tm = args.scan_inter_h
    pass
    self.log = LOG(self.log_file,self.log_level,self.log_max_size_bytes,
          self.log_bak_nums).GetLog()
  pass

class SmartScanDisks:
  def __init__(self, cmd_parser):
    self.cmd_parser = cmd_parser
    self.log  = cmd_parser.log
    self.scan_syslog_int_tm = cmd_parser.scan_sys_log_inter_tm 
    
    '''记录 raid disk原始列表 '''
    self.raid_scan_disk =list()  #不就是空列表吗，怎么不写[] ?
    '''记录hp logic volume disk 原始列表 '''
    self.hp_logic_volume_disk = list() 
    ''' 记录disks:可能是raw disk, or raid disk '''
    self.scan_disk = list()
     
    '''记录raid/raw disk下所有支持smartctl --scan 得到的raw disk,
    最终 raw_scan_disk 会和 scan_disk 项对应起来，至少个数和对应的顺序会保持一致'''
    self.raw_scan_disk = list() 
    
    '''默认是0:纯裸盘,1:纯raid, 2:hp logic volume '''
    self.disks_type = 0
  
  def IsRawDisk(self):
    return self.disks_type == 0  #返回逻辑关系，假或真
  def IsRaidDisk(self):
    return self.disks_type == 1
  def IsHpLogicVolume(self):
    return self.disks_type == 2

  def GetDiskTypes(self):
    return self.disks_type

  def GetScanDisks(self):
    return self.scan_disk 
  def GetRawDisks(self):
    return self.raw_scan_disk

  def GetRaidScanDisks(self):
    return self.raid_scan_disk

  def PackageScanDiskShell(self):  #检查盘类型命令
    str_scan_disk = "/usr/sbin/smartctl --scan|awk '{ if (NF <=7) print $1 }'"
    str_scan_raid = "/usr/sbin/smartctl --scan|awk '{ if (match($3,\"megaraid\")) print $3,$1 }'"
    str_scan_hp_logic_vol = "lsscsi -g |awk '{print $3, $4, $5,$7,$8,$1}'"
    return {'raw_disk':str_scan_disk,'raid_disk':str_scan_raid,
            'hp_logic_vol':str_scan_hp_logic_vol}
            
  def CheckCurrentDiskBusi(self):  #检测当前磁盘是否busy
    '''
    return: {1:busi, 0: not busi}
    '''
    iostat_cmd_str = "iostat -d -x "
    ret_child = self.RunDiskScanCmd(iostat_cmd_str);
    if len(ret_child[1]) != 0:
      self.log.error("cmd: % err: %s" % (iostat_cmd_str, ret_child[1]))
      return False
    
    begin_line = 0
    index_util = -1 
    list_utils = []
    for item in ret_child[0].split('\n'):
      y = item.strip()
      if len(y) == 0:
        continue
      if begin_line == 1:
        list_items = y.split()
        try:
          index_util = list_items.index('%util')
          self.log.debug("%s, %d" %(list_items,index_util))
        except ValueError:
          self.log.error("cmd: %s has not util item" % iostat_cmd_str)
          return False
      if begin_line < 2:
        begin_line += 1
        continue
      disk_io_stat = y.split()
      if index_util >=0 :
        list_utils.append(float(disk_io_stat[index_util]))
    
    assert(len(list_utils) > 0)
    if len(list_utils) != 0: 
      util_used = sum(list_utils)/len(list_utils)   #算出%utils的平均值
      self.log.debug("disk util used: %f" % (util_used))
      if util_used > 80.0:
        return True
    return False 

  def CheckTestType(self):
    '''
      :return: {-1: err, 0:timing_run, 1:io_cond_run}
      if timing run, do next step
      if io_cond_run, gather io current status, if busi
         return false: not to scan
         else do next step
    '''
    if self.cmd_parser.test_type not in ['timing_run','io_cond_run']:
      self.log.error("test type param is not: timing_run or io_cond_run")
      return -1
    elif self.cmd_parser.test_type == 'timing_run':
      self.log.debug("test type is: timing_run")
      return 0 
    else:
      self.log.debug("test type is: io_cond_run")
      return 1
  def GetSmartctlICmd(self, disk_sym, cmd): #运行相应的命令，返回了对应的信息
    smartctli_info = []
    ret_child = self.RunDiskScanCmd(cmd)
    if len(ret_child[1]) != 0:
      return smartctli_info 
    elif len(ret_child[0]) == 0:
      return smartctli_info 
    else:
      self.log.debug("cmd: %s,ret: %s" %(cmd, ret_child[0]))
      for x in ret_child[0].split('\n'):
        y = x.strip()
        if len(y) == 0:
          continue
        smartctli_info.append(y)
    return smartctli_info

  def GetSmartctlIHpLogicV(self,disk_sym):
    cmd_support = "/usr/sbin/smartctl -i -d cciss," + disk_sym
    return self.GetSmartctlICmd(disk_sym, cmd_support)

  def GetSmartctlIRaidDisk(self, disk_sym):
    cmd_support = "/usr/sbin/smartctl -i -d " + disk_sym
    return self.GetSmartctlICmd(disk_sym, cmd_support)

  def GetSmartctlIRawDisk(self, disk_sym):
    cmd_support = "/usr/sbin/smartctl -i " + disk_sym
    return self.GetSmartctlICmd(disk_sym, cmd_support)

  def IsSmartctlSupport(self, disk_sym,type = 0): #检测磁盘是否支持SMART
    '''type default 0: raw disk
        1: raid disk, 2: hp logic vol 
    '''
    ret_smartctl_i_disk = None 
    if type == 0:
      ret_smartctl_i_disk = self.GetSmartctlIRawDisk(disk_sym)
    elif type == 1:
      ret_smartctl_i_disk = self.GetSmartctlIRaidDisk(disk_sym) #运行检查raid盘的命令cmd_support = "/usr/sbin/smartctl -i -d " + disk_sym后的信息存入变量
    elif type == 2:
      ret_smartctl_i_disk = self.GetSmartctlIHpLogicV(disk_sym)
    else:
      return False

    if len(ret_smartctl_i_disk) == 0:
      return False
    for x in ret_smartctl_i_disk:
      pattern = re.compile(r'SMART support is:\s*Available')
      match = pattern.match(x)
      if match:
        self.log.debug("smart is support by disk: %s" % disk_sym)
        return True
    return False 

  def EnableSmartctl(self, disk_sym,type = 0):
    ''' type: 0 raw disk, 1: raid disk'''
    cmd_enable_smartctl  = None
    if type == 0:
      cmd_enable_smartctl = "/usr/sbin/smartctl -s on " + disk_sym
    elif type == 1:
      cmd_enable_smartctl = "/usr/sbin/smartctl -s on -d " + disk_sym
    elif type == 2:
      cmd_enable_smartctl = "/usr/sbin/smartctl -s on -d cciss," + disk_sym
    else:
      return False
    ret_child = self.RunDiskScanCmd(cmd_enable_smartctl)
    if len(ret_child[1]) != 0:
      return False 
    elif len(ret_child[0]) == 0:
      return False 
    else:
      pass 
    return True

  def IsEnableSmartctl(self, disk_sym, type = 0):
    '''type: 0 raw disk, 1: raid disk, 2: hp logic volume'''
    ret_smartctl_i_disk = None 
    if type == 0:
      ret_smartctl_i_disk = self.GetSmartctlIRawDisk(disk_sym)
    elif type == 1:
      ret_smartctl_i_disk = self.GetSmartctlIRaidDisk(disk_sym)
    elif type == 2:
      ret_smartctl_i_disk = self.GetSmartctlIHpLogicV(disk_sym) 
    else:
      return False
    if len(ret_smartctl_i_disk) == 0:
      return False

    for x in ret_smartctl_i_disk:
      pattern = re.compile(r'SMART support is:\s*Enabled')
      match = pattern.match(x)
      if match:
        self.log.debug("smart enabled for disk: %s" % disk_sym)
        return True
      pattern = re.compile(r'SMART support is:\s*Disabled')
      match = pattern.match(x)
      if match:
        self.log.debug("smart disabled for disk: %s" % disk_sym)
        if self.EnableSmartctl(disk_sym, type) == True:
          self.log.info("succ enable on for disk: %s" % disk_sym)
          return True 
        else:
          self.log.info("enable on failed for disk: %s" % disk_sym)
    return False
  
  def FindRawDiskByRaidDiskIndex(self, disk_info):
    try:
      index_n = self.raid_scan_disk.index(disk_info)
      one_raw_disk = self.raw_scan_disk[index_n]
      return one_raw_disk 
    except ValueError as e:
      self.log.error("has not node,err: %s" % e)
      return None

  def FindRawDiskByHpLogVIndex(self, disk_info):
    try:
      index_n = self.hp_logic_volume_disk.index(disk_info)
      one_raw_disk = self.raw_scan_disk[index_n]
      return one_raw_disk 
    except ValueError as e:
      self.log.error("has not node,err: %s" % e)
      return None

  def EnableSupportSmart(self, disk_lists, type = 0):  #函数返回真或假。返回真说明盘都是支持smart的
    ''' disk_lists:  是真实采集到的磁盘列表'''
    '''type: 0 raw disk ; 1: raid disk; 2: hp logic vol '''
    temp_raw_disk = list()
    for dskinfo in disk_lists:
      self.log.debug("dev: %s" % dskinfo)
      if self.IsSmartctlSupport(dskinfo,type) == False:
        self.log.error("smartctl not supported for disk: %s " 
            % dskinfo)
        continue
      if self.IsEnableSmartctl(dskinfo,type) == False:
        self.log.error("enable smartctl failed on disk: %s " 
            % dskinfo)
        continue
      ## 
      one_disk = None
      if self.IsRaidDisk():
        '''获取raid下 对应的有效 raw disks'''
        one_disk = self.FindRawDiskByRaidDiskIndex(dskinfo) #通过raid盘的索引查找raw盘
        if one_disk == None:
          return False
      elif self.IsHpLogicVolume():
        one_disk = self.FindRawDiskByHpLogVIndex(dskinfo)
        self.log.debug("hp logic disk to raw disk: %s", one_disk)
        if one_disk == None:
          return False
      else:
        pass 
      temp_raw_disk.append(one_disk) ###raw disks
      self.scan_disk.append(dskinfo) ###actual scan disks  这里是真正打命令出来看到的所有磁盘列表raw or raid , hp_logic
    if len(self.scan_disk) == 0:
      return False
    if self.IsRaidDisk() or self.IsHpLogicVolume():
      self.raw_scan_disk = temp_raw_disk 
      '''获取hp logic volume 对应的raw disks '''
    else:
      self.raw_scan_disk = self.scan_disk
      pass 
    self.log.debug("actual scan disk: %s", self.scan_disk)
    self.log.debug("raw disk: %s", self.raw_scan_disk)
    return True

  def FilterRaidScanDisk(self, in_str_disk):
    '''like this format: /dev/bus/0 megaraid,8 
    '''
    tmp_disk_list = in_str_disk.split('\n')
    disk_list = []
    for x in tmp_disk_list:
      if len(x) == 0:
        continue
      disk_list.append(x)
    return disk_list

  def FilterScanDisk(self, in_str_disk):
    str_disk = in_str_disk.strip() 
    tmp_disk_list = str_disk.split('\n')
    disk_list = []
    for x in tmp_disk_list:
      y = x.strip()
      if len(y) == 0:
        continue
      disk_list.append(y)
    return disk_list

  def RunDiskScanCmd(self, cmd):
    child = subprocess.Popen(cmd,shell=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    ret_child = child.communicate()   # returns a tuple (stdout, stderr).
    return ret_child
  
  def FilterHpLogicvol(self,in_str_disk):
    str_disk = in_str_disk.strip()
    tmp_disk_list = str_disk.split('\n')
    disk_list =  []
    for x in tmp_disk_list:
      y = x.strip()
      if len(y) == 0:
        continue
      disk_list.append(y)
    return disk_list 
  
  # return hplogic volume, is list,format is: i /dev/sg*
  def CheckIsHPLogicVolume(self):  #检测是否hplogic，返回值是hplogic列表
    hp_logic_vol_list = []
    ret_hp_logic_vol_list = []
    cmd_scan_disk = self.PackageScanDiskShell()
    ret_hp_logic_child = self.RunDiskScanCmd(cmd_scan_disk['hp_logic_vol'])
    if len(ret_hp_logic_child[1]) != 0:
      self.log.error("cmd %s failed, err: %s" 
          % (cmd_scan_disk['hp_logic_vol'],str(ret_hp_logic_child[1])))
      return []
    hp_logic_vol_list = self.FilterHpLogicvol(ret_hp_logic_child[0])
    for x in  hp_logic_vol_list:
      y = x.split()
      if len(y) != 6: 
        continue
      if y[0] != "HP" and y[1] != "LOGICAL" and y[2] != "VOLUME":
        continue
      index_sym_cmd = "echo " + y[5] + " |awk -F\":\" '{print $4}' |awk -F\"]\" '{print $1}'" 
      ret_index_cmd = self.RunDiskScanCmd(index_sym_cmd)  #获取hp_logic盘的索引
      if len(ret_index_cmd[1]) != 0:
        continue
      temp_str = ret_index_cmd[0].strip()
      if len(temp_str) == 0:
        continue
      ''' format is: num  /dev/sg* '''
      str_tmp_item = temp_str + " " +  y[4]  
      ret_hp_logic_vol_list.append(str_tmp_item)
    pass 
    self.log.debug(ret_hp_logic_vol_list)
    return ret_hp_logic_vol_list 

  def ScanDisk(self):  #扫描磁盘并做启用smart操作。这函数会判断这台机器属于哪种类型的盘。 返回值是真或假
    '''
      return 0: err, 1: succ, 2: not to do next steps
    '''
    cmd_scan_disk = self.PackageScanDiskShell() #返回一个字典，key是什么盘，值是检查这种盘的命令
    str_cmd = "" 
    for k,v in cmd_scan_disk.items():
      print("%s: %s" % (k,v))
      str_cmd += k
      str_cmd +=":"
      str_cmd += v 
      str_cmd += " "
    self.log.debug("smartctl scan disk cmd: %s" % str_cmd)
    ck_ret = self.CheckTestType()  #根据命令行里面指定对盘的检查类型，-1: err, 0:timing_run, 1:io_cond_run
    if ck_ret == -1:
      return False
    elif ck_ret == 1:  #检查3次，如果繁忙返回2，不繁忙啥也不做
      try_nums = 3
      while try_nums > 0:
        if self.CheckCurrentDiskBusi() == True:
          self.log.info("io busi, need not to been scaned")  #通过util的平均值来判断磁盘是否空闲，如果空闲就继续下一步，不空闲就退出不扫描磁盘
          return 2 
        try_nums -= 1
        time.sleep(1)
    else:  #针对0:timing_run没写代码
      pass

    ret_raid_child = self.RunDiskScanCmd(cmd_scan_disk['raid_disk']) #运行检查raid盘的命令后的输出存入这个变量，是一个元组
    if len(ret_raid_child[1]) != 0:
      self.log.error("cmd %s failed, err: %s" % 
          (cmd_scan_disk['raid_disk'], str(ret_raid_child[1])))
      return False
    raid_disks_list = self.FilterRaidScanDisk(ret_raid_child[0]) #返回raid盘列表['megaraid,0 /dev/bus/0', 'megaraid,1 /dev/bus/0']
    #######################################################
    #######################################################
    ret_rawdisk_child = self.RunDiskScanCmd(cmd_scan_disk['raw_disk'])
    if len(ret_rawdisk_child[1]) != 0:
      self.log.error("cmd %s failed, err: %s" % 
          (cmd_scan_disk['raw_disk'], str(ret_rawdisk_child[1])))
      return False
    raw_disks_list = self.FilterScanDisk(ret_rawdisk_child[0]) #返回裸盘列表

    if len(raid_disks_list) != 0:
      if len(raw_disks_list) != len(raid_disks_list): 
        self.log.error("raw disk nums not eq raid disk nums")
        return False
    #
    self.log.debug("raid scan disks: %s " % raid_disks_list)
    self.log.debug("raw scan disks: %s " % raw_disks_list)
    #
    if len(raid_disks_list) != 0:
      # do enable by raid
      self.disks_type = 1
      '''记录真正的disks: --scan 得到的磁盘'''
      self.raw_scan_disk = raw_disks_list 
      self.raid_scan_disk = raid_disks_list
      return self.EnableSupportSmart(raid_disks_list,1)
    else:
      # do enable by raw
      hp_logic_volume_disk = self.CheckIsHPLogicVolume()  #检测是否hplogic，并返回hplogic列表
      if len(hp_logic_volume_disk) != 0:
        if len(hp_logic_volume_disk) != len(raw_disks_list):
          self.log.error("hp logic volume nums not eq raw disk nums")
          return False
        pass
        self.disks_type = 2
        '''记录真正的disks:--scan 得到的磁盘'''
        self.raw_scan_disk = raw_disks_list  
        self.hp_logic_volume_disk =  hp_logic_volume_disk
        return self.EnableSupportSmart(hp_logic_volume_disk,2)
      else:
        ''' --scan 得到的磁盘'''
        self.disks_type = 0
        self.raw_scan_disk = raw_disks_list 
        return self.EnableSupportSmart(raw_disks_list, 0)

class FileOP:
  def __init__(self, log, filename, mode ='w+'):
    ''' should write the temp file, when 
    write all done, then move the temp file to last file 
    '''
    self.log = log
    self.filename = filename
    
    self.tmp_filename = filename + ".bak"
    self.tmp_fd = open(self.tmp_filename, mode)
    self.mode = mode
  
  def GetScanDiskInfoDBFile(self):
    return self.filename

  def RenameBakFileToFinalFile(self):
    try:
      os.rename(self.tmp_filename, self.filename) 
    except:
      self.log.error("rename tmp file to last file err")
      return False
    return True

  def WriteFile(self, data):
    try:
      self.tmp_fd.write(data)
      self.tmp_fd.write('\n')
      self.tmp_fd.flush()
    except: 
      self.log.error("write data to file err,file: %s " % self.tmp_filename)
      return False
    return True

  def ReadFile(self):
    return []
  def __del__(self):
    if not self.tmp_fd and self.tmp_fd.closed == False:
      self.tmp_fd.close()
      self.tmp_fd = None
      self.log.debug("close open fd")


class ReportDiskSmartInfo:
  def __init__(self,scan_disks,cmd_parser, scan_file):
    self.scan_disks = scan_disks
    self.cmd_parser = cmd_parser
    self.scan_file = scan_file
    self.scan_sys_log_inter_tm = cmd_parser.scan_sys_log_inter_tm 
    ''' likes {'disk1':
                  {'is_health': 'ok',
                   'disk_to_fail':'no',
                   'disk_tool_old':'no',
                   'value_thresh': 'lt',
                   'Spin_Retry_Count':1000,
                   'Reallocated_Sector_Ct':1999
                   }, 
                   'disk2': {} 
               }'''
    self.scan_status = dict() 
    self.pure_A_cmd_ret = []
    self.log = cmd_parser.log
    pass
  def IsRaidDisk(self):
    return self.scan_disks.IsRaidDisk()
  def IsRawDisk(self):
    return self.scan_disks.IsRawDisk()
  def IsHpLogicVolume(self):
    return self.scan_disks.IsHpLogicVolume()

  def ShowScanDiskStatus(self):
    self.log.debug("scan disk type: %d " %  self.scan_disks.GetDiskTypes())
    self.log.debug("health for all disks: %s " % str(self.scan_status))

  def SendScanInfoToZbx(self):
    send_cmd_str = "zabbix_sender -I " + self.cmd_parser.ip + " "
    send_cmd_str += ' -p ' + str(self.cmd_parser.port)  + " "
    send_cmd_str += ' -c ' + self.cmd_parser.zbx_conf  + " "
    send_cmd_str += ' --input-file ' + self.scan_file.GetScanDiskInfoDBFile() 
    self.log.debug("send cmd : {0}".format(send_cmd_str))

    ret = self.scan_disks.RunDiskScanCmd(send_cmd_str)
    self.log.info("cmd: %s  ,ret: %s " % (send_cmd_str, ret[0]))
    if len(ret[1]) != 0:
      self.log.error("cmd: %s, err: %s" %(send_cmd_str,ret[1]))
      return False
    else:
      return True

  def ScanDiskInfoToDB(self):
    ''' format of items likes: 
        hostname  item[disk]    item_val
        hostname  item.k[disk]  item_val
      '''
    for disk, scan_items in self.scan_status.items():
      self.log.debug("k: %s, val: %s" % (disk, scan_items))
      str_host_name = self.cmd_parser.host + " "
      
      for item, item_v in scan_items.items():
        str_v_to_db = str_host_name + item + "[" +  disk  +"]" + " " + str(item_v)
        self.scan_file.WriteFile(str_v_to_db)
    pass 
    return self.scan_file.RenameBakFileToFinalFile()
    
  def CheckSmartctlHRet(self, ret_health):
    ret_list = []
    for x in ret_health.split('\n'):
      y = x.strip()
      if len(y) == 0:
        continue
      ret_list.append(y)
    
    for x in ret_list:
      pattern = re.compile(r'SMART overall-health self-assessment test result:\s*PASSED')
      match = pattern.match(x)
      if match:
        self.log.debug("smartclt -H is health")
        return True
      pattern = re.compile(r'SMART Health Status:\s*OK')
      match = pattern.match(x)
      if match:
        self.log.debug("smartctl -H is health")
        return True
    return False
 
  def UpdateDiskHealthStatus(self, is_health, disk_sym):
    health_val = None 
    if is_health == False:
      health_val = 0 
    else:
      health_val = 1
     
    disk_status = self.scan_status.get(disk_sym) #disk_status是一个字典
    if disk_status == None:
       disk_info = dict()
       disk_info['is_health'] = health_val 
       self.scan_status[disk_sym] = disk_info
    else:
      health_item = disk_status.get('is_health')
      self.scan_status[disk_sym][is_health] = health_val

  ## scan sys mesg log,return error disk list, scan process items' timestamp 
  # > now - inter_tm
  def ScanSysMesgLog(self,ret_scan_list):   #扫描不超过3小时的/var/log/messages日志，如果发现磁盘告警就打印到自定义的日志文件，并返回逻辑值 真
    months_31 = ['Jan','Mar','May','Jul','Aug','Oct','Dec']
    months_30 = ['Apr','Jun','Sep','Nov']
    month_28or29 = 'Feb'
    months = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
        'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}
    month_days = {}
    for mon in months_31:
      month_days[mon] = 31
    #
    for mon in months_30:
      month_days[mon] = 30
    #
    if date.isocalendar(date.today())[0]%4 == 0:
      month_days[month_28or29] = 29
    else:
      month_days[month_28or29] = 28
    now_tm = datetime.now()
    str_now_month = now_tm.strftime('%b')
    str_now_day = now_tm.strftime('%d')
    str_now_hour = now_tm.strftime('%H')
    self.log.debug("now => moth: %s, day: %s, hour: %s", str_now_month,
        str_now_day, str_now_hour)
    lines = list()
    #open sys messages file:
    #scan_log_file = "./test_messages"
    scan_log_file = "/var/log/messages"
    self.log.debug("scan log file: %s", scan_log_file)
    mesg_log_fd = None
    try:
      mesg_log_fd = open(scan_log_file)
    except Exception as err:
      self.log.error("open /var/log/messages failed, err: %s", err) 
      return False
    except:
      self.log.debug("catch all error when open file")
      return False
    for line in mesg_log_fd:
      line = line.split('\n')[0]
      if len(line.strip()) == 0:
        continue
      #self.log.debug("line: %s", line)
      str_hour = line.split()[2].split(':')[0]
      int_hour = int(str_hour)
      if line.split()[0] == str_now_month: ## the same month
        if int(line.split()[1]) == int(str_now_day): ## the same day
          if int(str_now_hour) - int_hour <= self.scan_sys_log_inter_tm \
              and int(str_now_hour) > int_hour:
            self.log.debug("scan line is vailed, line: %s", line)  #扫描不超过自己设定的时间阀值的日志，默认阀值是3，那就是不扫描超过3小时的日志
            lines.append(line)
        elif int(str_now_day) - int(line.split()[1]) == 1:  ## before one day.
          if int(str_now_hour) + 24 - int_hour < self.scan_sys_log_inter_tm:
            self.log.debug("scan line is vailed, log mesg: %s", line)
            lines.append(line)
        else:
          pass 
      elif (months[str_now_month] - months[line.split()[0]]) == 1 or (
          months[str_now_month] - months[line.split()[0]]) == -11:
        if int(str_now_day) + month_days[line.split()[0]] - int(line.split()[1]) == 1:
          if int(str_now_hour)+24 - int_hour <= self.scan_sys_log_inter_tm:
            self.log.debug("scan line is vailed, log mesg: %s", line)
            lines.append(line)
      else:
          pass
    mesg_log_fd.close()
    pass
    self.log.debug("scan lines: %s", lines)
    pattern = 'end_request: I/O error'
    Medium_pattern = 'end_request: critical medium error'
    critical_pattern = 'end_request: critical target error'
    for line in lines:
      match = re.search(pattern,line)
      if match:
        self.log.debug("disk error scan Buffer I/O from messages, line: %s",line)
        err_disk = line.split()[8].split(',')[0];
        ret_scan_list.append(err_disk)
      Medium_match = re.search(Medium_pattern,line)
      if Medium_match:
        self.log.debug("disk error scan Medium from messages, line: %s",line)
        err_disk = line.split()[9].split(',')[0];
        ret_scan_list.append(err_disk)
      match = re.search(critical_pattern,line)
      if match:
        self.log.debug("disk error scan critical err from messsages, line: %s",line)
        err_disk = line.split()[9].split(',')[0];
        ret_scan_list.append(err_disk) 
    return True
  # return boolean, inparam: list_scan_disk is [sda,sdb,....]
  # dest_disk is /dev/sda or /dev/sdb or ...
  def CheckDiskInSysMesgErrLog(self,list_scan_disk, dest_disk):  #检查磁盘是否在日志里面出现
    scan_disks = self.scan_disks.scan_disk  # 这里的磁盘列表是 EnableSupportSmart 这个函数里面获取到的
    if not (dest_disk in scan_disks):
      return False
    index_disk = scan_disks.index(dest_disk)
    actual_disk = self.scan_disks.raw_scan_disk[index_disk]
    simple_disk_sym = actual_disk.split('/')[-1:][0]
    self.log.debug("post-index disk sym: %s,orig disk: %s", 
        simple_disk_sym, actual_disk)
    ret = False
    if simple_disk_sym in list_scan_disk:
      self.log.info("disk: %s in message log ", simple_disk_sym)
      ret = True
    else:
      self.log.info("disk: %s not in message log", simple_disk_sym)
    return ret

  def CheckDisksHealth(self):
    disk_type = self.scan_disks.GetDiskTypes()
    scan_disks = self.scan_disks.GetScanDisks() ##actual scan disks
    smartctl_H_cmd = '/usr/sbin/smartctl -H '
    #assert(disk_type  == 2)
    if self.scan_disks.IsRaidDisk(): 
      ''' raid disk '''
      smartctl_H_cmd += ' -d '
    if self.scan_disks.IsHpLogicVolume():
      ''' hp logic volum '''
      smartctl_H_cmd += ' -d cciss,'
    #
    ret_scan_disk_from_syslogmsg = list()
    self.ScanSysMesgLog(ret_scan_disk_from_syslogmsg)
    self.log.debug("scan invaild disk: %s", ret_scan_disk_from_syslogmsg) #因为是列表，所以在self.ScanSysMesgLog(ret_scan_disk_from_syslogmsg)执行完后，这个列表有值了
    for x in scan_disks:
      cmd = smartctl_H_cmd + x 
      ret_child = self.scan_disks.RunDiskScanCmd(cmd)
      if len(ret_child[1]) != 0:
        self.log.error("excuate failed, cmd: %s " % cmd)
        continue
      elif len(ret_child[0]) == 0:
        self.log.error("excuate ret empty, cmd: %s " % cmd)
        continue
      else:
        self.log.debug("cmd: %s, ret: %s" % (cmd, ret_child[0]))
        ret = self.CheckSmartctlHRet(ret_child[0]) #判断磁盘是否健康
        ##scan sys log messages, if has error info, then return True
        ret_scan_sys_log = self.CheckDiskInSysMesgErrLog(
            ret_scan_disk_from_syslogmsg, x)
        ret = ret and (not ret_scan_sys_log) 
        self.UpdateDiskHealthStatus(ret,x)
        pass
    self.log.debug("check is health cmd")
    self.ShowScanDiskStatus()

  def UpdateDiskAStatus(self, A_cmd_ret, disk_sym):
    ret_list = []
    for x in A_cmd_ret.split('\n'):
      y = x.strip()
      if len(y) == 0:
        continue
      ret_list.append(y)

    line_begin = 0
    str_begin_line = None
    for x in ret_list:
      pattern = re.compile(r'Vendor Specific SMART Attributes with Thresholds:')
      match = pattern.match(x)
      if match:
        self.log.debug("find promot flag")
        line_begin += 1
        continue
      else:
        if line_begin > 0 and line_begin < 2:
          line_begin += 1
        elif line_begin >= 2:
          str_begin_line = x;
          break
        else:
          continue
    if str_begin_line != None:
      index_n = ret_list.index(str_begin_line)
      self.pure_A_cmd_ret  = ret_list[index_n:]
    else:
      return None
    self.log.debug("A cmd item nums: %d, disk: %s" % \
        (len(self.pure_A_cmd_ret),disk_sym))
    for x in self.pure_A_cmd_ret:
      one_item_list = x.split()
      attr_name = one_item_list[1]
      value_dat = int(one_item_list[3])
      thresh_dat = int(one_item_list[5])
      flag_value_thresh = False 
      '''该值的VALUES过高，那么在未来磁盘失效的情况更高 '''
      flag_reallocated_sector_ct = False 
      '''该值的values 不断增加，表示 a sign of problems in the hard disk mechanical subsystem '''
      flag_spin_retry_count = False
      
      if value_dat < thresh_dat:
        self.log.error("%s 's  attr: %s  is abnormal",disk_sym,attr_name)
        flag_value_thresh  = True

      reall_setor_ct_cond = attr_name == 'Reallocated_Sector_Ct' \
          and float(value_dat) > 0.9*255
      if reall_setor_ct_cond: 
          self.log.error("%s attr: %s is high" % (disk_sym, attr_name))
          flag_reallocated_sector_ct = True
      if attr_name == 'Spin_Retry_Count':
        self.log.info("report this attr:Spin_Retry_Count value")
        flag_spin_retry_count  = True
      
      #other attr as: TYPE{Pre-fail, Old_age} not to been reported
      disk_status = self.scan_status.get(disk_sym)
      if disk_status == None:
        self.scan_status[disk_sym] = {}

      if flag_value_thresh == True:
        item_name = 'value_thresh'
        self.scan_status[disk_sym][item_name] = 1
        self.log.debug("disk: %s, attr: %s, value: %d",
            disk_sym, item_name, self.scan_status[disk_sym][item_name])
      else:
        item_name = 'value_thresh'
        ret = self.scan_status[disk_sym].get(item_name)
        if ret == None:
          self.scan_status[disk_sym][item_name] = 0 
      #####
      if flag_reallocated_sector_ct == True:
        item_name ='Reallocated_Sector_Ct' 
        self.scan_status[disk_sym][item_name] = value_dat 
        self.log.info("disk: %s, attr: %s, value: %s",
            disk_sym, item_name, str(value_dat))
      else:
        item_name ='Reallocated_Sector_Ct' 
        ret = self.scan_status[disk_sym].get(item_name)
        if ret == None:
          self.scan_status[disk_sym][item_name] = 0 
      ####
      if flag_spin_retry_count == True:
        item_name = 'Spin_Retry_Count' 
        ret = self.scan_status[disk_sym].get(item_name)
        if ret == None:
          self.scan_status[disk_sym][item_name] = value_dat
    pass

  def SmartCtlA(self):
    disk_type = self.scan_disks.GetDiskTypes()
    scan_disks = self.scan_disks.GetScanDisks()
    smartctl_A_cmd = "/usr/sbin/smartctl -A "
    if self.scan_disks.IsRaidDisk():
      ''' raid disk '''
      smartctl_A_cmd += ' -d '
    
    if self.scan_disks.IsHpLogicVolume():
      ''' hp logic volum '''
      smartctl_A_cmd += ' -d cciss,'
    
    for x in scan_disks:
      cmd = smartctl_A_cmd + x
      ret_child = self.scan_disks.RunDiskScanCmd(cmd) 
      if len(ret_child[1]) != 0:
        self.log.error("execuate ret empty, cmd: %s " % cmd)
        continue
      elif len(ret_child[0]) == 0:
        self.log.error("execute ret empty,cmd: %s " % cmd)
        continue
      else:
        self.log.debug("cmd: %s, ret: %s" % (cmd, ret_child[0]))
        self.UpdateDiskAStatus(ret_child[0],x)
     
    if self.IsRaidDisk():   #如果是raid盘，就转化为真实的裸盘的健康状态
      temp_status = dict()
      print(self.scan_status)
      for key_tmp in  self.scan_status.keys():
        index_n = self.scan_disks.GetScanDisks().index(key_tmp)
        raw_disk_name = self.scan_disks.GetRawDisks()[index_n]
        temp_status[raw_disk_name] = self.scan_status[key_tmp]
      pass 
      self.scan_status = temp_status
    if self.IsHpLogicVolume():
      temp_status = dict()
      self.log.debug("before: {0}".format(self.scan_status))
      for key_tmp in self.scan_status.keys():
        index_n = self.scan_disks.GetScanDisks().index(key_tmp)
        raw_disk_name = self.scan_disks.GetRawDisks()[index_n]
        temp_status[raw_disk_name] = self.scan_status[key_tmp]
      pass
      self.scan_status = temp_status

    self.log.debug("check smartctl -A cmd")
    self.ShowScanDiskStatus()

  def ReportDiskInfo(self):
    self.CheckDisksHealth()  #检查磁盘健康状态
    self.SmartCtlA()   #检查磁盘的各项指标是否超过阀值
    self.ScanDiskInfoToDB()   #把检查结果存入文件
    self.SendScanInfoToZbx() #把检查结果发到zabbix服务器
  pass


def main_run():
  cmd_parser = CmdParse()
  cmd_parser.ParseCmd()   #命令行解析工具，方便你自定义添加各种参数
  
  tm_elapse = TimeElapse(cmd_parser.log,"scan disk info") #初始化磁盘扫描时间
  
  scan_disk = SmartScanDisks(cmd_parser)  #创建磁盘扫描对象
  ret_scan = scan_disk.ScanDisk() #扫描磁盘
  if False == ret_scan :
    cmd_parser.log.error("scan disk failed, exit now")
    exit()
  elif ret_scan == 2 :
    cmd_parser.log.info("disk is busi, not to scan and report")
    exit()
  else:
    cmd_parser.log.info("scan disk status succ")
  
  file_name = os.path.join(cmd_parser.store_scan_diskdat_path, 
      "zbx_sender_scandisk.conf")
  scan_data_file = FileOP(cmd_parser.log, file_name)

  report_disk_smartctl = ReportDiskSmartInfo(scan_disk,
      cmd_parser,scan_data_file);
  report_disk_smartctl.ReportDiskInfo()
  pass
  del(tm_elapse)

if __name__ == '__main__':
  main_run()

  
