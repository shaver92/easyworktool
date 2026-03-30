# -*- coding: utf-8 -*-

# -------------------------------------------------------------------------------
# Name:         read
# Description:
# Author:       shaver
# Date:         2026/1/12
# -------------------------------------------------------------------------------


# 读取整个目录下的txt文件的内容
import os

def read_txt(path):
    files = os.listdir(path)
    for file in files:
        if file.endswith('.txt'):
            # 打印文件名称
            print(file)
            with open(os.path.join(path, file), 'r', encoding='utf-8') as f:
                content = f.read()
                print(content)

if __name__ == '__main__':
    read_txt('/Users/shaver/Downloads/2.资料/4.图灵课堂java-第八期/02 框架源码')