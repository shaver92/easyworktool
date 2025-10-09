# -*- coding: utf-8 -*-

# -------------------------------------------------------------------------------
# Name:         app
# Description:  电商数据整理app
# Author:       shaver
# Date:         2025/9/10
# -------------------------------------------------------------------------------
import streamlit as st
import pandas as pd

# 1 导入excel文件


# 2 导入数据
df = pd.read_excel('data.xlsx')

# 显示在页面上
st.write(df)
