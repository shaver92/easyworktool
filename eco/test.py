# -*- coding: utf-8 -*-

# -------------------------------------------------------------------------------
# Name:         test
# Description:  编写一个程序 指定行的所有列名，并将结果写入txt文件中。
# Author:       shaver
# Date:         2025/9/9
# -------------------------------------------------------------------------------

import pandas as pd

# 读取excel文件的指定sheet
excel_path = '/Users/shaver/Desktop/data/模板.xlsx'

# 获取所有的sheet名称
# sheets = pd.ExcelFile(excel_path).sheet_names
#
# 子表
# 业务报告
# WT报告
# SP
# SD
# SB
# Base

# 读取指定行的所有数据
row = 2
sheet_name = '子表'

df = pd.read_excel(excel_path, sheet_name=sheet_name)


cols = df.iloc[row]



# 获取每个单元格里面的函数fx

# 写入txt文件 名称为sheet_name+'.txt'
with open(sheet_name+'.txt', 'w') as f:
    for col in cols:
        # 去除换行符
        col = col.replace('\n', '')
        f.write(col+'\n')