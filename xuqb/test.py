#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2017-08-21 11:29:02
# @Author  : wuwei
# @Link    : 
# @Version : v1.0


from lxml import etree

class DataSource:
    data = [ b"<roo", b"t><", b"a/", b"><", b"/root>" ]
    def read(self, aa):
        try:
            return self.data.pop(0)
        except IndexError:
            return b''

tree = etree.parse(DataSource())

print etree.tostring(tree)
	
#if __name__ == "__main__":
 #    for i in range(1, 201):
#	    print generate_activation_code()