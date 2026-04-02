# -*- coding: utf-8 -*-

# -------------------------------------------------------------------------------
# Name:         home
# Description:  考勤信息汇总工具
# Author:       shaver
# Date:         2025/7/1
# -------------------------------------------------------------------------------
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime, time


def _parse_excel_clock_cell(v):
    """将 Excel 读出的打卡时间统一为 datetime.time（列内常混有 time 与字符串）。"""
    if pd.isna(v):
        return pd.NaT
    if isinstance(v, time):
        return v
    if isinstance(v, datetime):
        return v.time()
    if isinstance(v, pd.Timestamp):
        return v.time()
    if isinstance(v, str):
        s = v.strip().replace("::", ":")
        if not s:
            return pd.NaT
        for fmt in ("%H:%M:%S", "%H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).time()
            except ValueError:
                continue
        ts = pd.to_datetime(s, errors="coerce", format="mixed")
        return pd.NaT if pd.isna(ts) else ts.time()
    if isinstance(v, bool):
        return pd.NaT
    if isinstance(v, (int, float)):
        x = float(v)
        if not (x == x):  # NaN
            return pd.NaT
        if 0 <= x < 1:
            secs = int(round(x * 86400)) % 86400
            h, r = divmod(secs, 3600)
            m, sec = divmod(r, 60)
            return time(h, m, sec)
        ts = pd.to_datetime(x, unit="D", origin="1899-12-30", errors="coerce")
        return pd.NaT if pd.isna(ts) else ts.time()
    return pd.NaT


# 设置页面标题和布局
st.set_page_config(page_title="考勤信息汇总系统", layout="wide")
st.title("📊 考勤信息汇总系统")

# 添加侧边栏说明
with st.sidebar:
    st.header("使用说明")
    st.markdown("""
    1. 选择考勤日期范围
    2. 上传多个考勤Excel文件
    3. 点击"合并数据"按钮预览结果
    4. 确认无误后下载合并后的文件
    """)

# 选择考勤日期范围
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("开始日期", value=None, key="start_date")
with col2:
    end_date = st.date_input("结束日期", value=None, key="end_date")

# 日期范围验证
if start_date and end_date and start_date > end_date:
    st.error("错误：结束日期不能早于开始日期！")

# 上传考勤信息文件列表
file_list = st.file_uploader(
    "上传考勤信息文件(支持多选)",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
    help="请上传Excel格式的考勤文件"
)

# 显示上传的文件数量
if file_list:
    st.success(f"已成功上传 {len(file_list)} 个文件")

# 合并数据按钮
if st.button("🔽 合并数据", key="merge_button"):
    if not file_list:
        st.warning("请先上传考勤文件！")
    else:
        try:
            with st.spinner("正在处理数据，请稍候..."):
                df_list = []
                for file in file_list:
                    # 读取每个Excel文件的所有工作表
                    excel_data = pd.read_excel(file, sheet_name=None)
                    # 获取所有工作表的数据并添加到列表
                    for sheet_name, sheet_df in excel_data.items():
                        df_list.append(sheet_df)

                if df_list:
                    # 合并所有数据
                    df_all = pd.concat(df_list, ignore_index=True)

                    # 处理时间列 - 确保是时间类型
                    time_columns = ['上班打卡时间', '下班打卡时间']
                    for col in time_columns:
                        if col in df_all.columns:
                            # openpyxl 常把部分格读成 datetime.time，部分读成 str；整列 to_datetime 会把 time 变成 NaT
                            df_all[col] = df_all[col].map(_parse_excel_clock_cell)

                    # 筛选异常考勤数据
                    if all(col in df_all.columns for col in ['上班打卡时间', '下班打卡时间']):
                        # 定义正常工作时间
                        normal_start = time(9, 15)
                        normal_end = time(18, 15)

                        # 计算迟到早退
                        df_all['是否迟到'] = df_all['上班打卡时间'].apply(
                            lambda x: x > normal_start if pd.notnull(x) else False
                        )
                        df_all['是否早退'] = df_all['下班打卡时间'].apply(
                            lambda x: x < normal_end if pd.notnull(x) else False
                        )

                    # 显示合并后的数据预览
                    st.subheader("合并数据预览")
                    # 交互表格
                    st.dataframe(
                        df_all,
                        use_container_width=True,
                        height=600,  # 固定高度
                        column_config={
                            "是否迟到": st.column_config.CheckboxColumn("是否迟到"),
                            "是否早退": st.column_config.CheckboxColumn("是否早退")
                        }
                    )

                    # 显示统计信息
                    st.subheader("数据统计")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("总记录数", len(df_all))

                    if '姓名' in df_all.columns:
                        unique_names = df_all['姓名'].nunique()
                        col2.metric("涉及员工数", unique_names)

                    if '是否迟到' in df_all.columns:
                        late_count = df_all['是否迟到'].sum()
                        # 使用HTML标签实现红色显示
                        col3.markdown(f"""
                        <div style="font-size: 1.2rem; margin-bottom: 0.5rem;">迟到记录</div>
                        <div style="font-size: 1.5rem; color: red; font-weight: bold;">{late_count}</div>
                        """, unsafe_allow_html=True)

                    if '是否早退' in df_all.columns:
                        early_count = df_all['是否早退'].sum()
                        # 使用HTML标签实现红色显示
                        col4.markdown(f"""
                        <div style="font-size: 1.2rem; margin-bottom: 0.5rem;">早退记录</div>
                        <div style="font-size: 1.5rem; color: red; font-weight: bold;">{early_count}</div>
                        """, unsafe_allow_html=True)
                    # 提供下载按钮
                    st.subheader("下载合并文件")

                    # 创建Excel文件
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_all.to_excel(writer, index=False, sheet_name='汇总数据')

                    output.seek(0)

                    # 生成下载按钮
                    st.download_button(
                        label="📥 下载Excel文件",
                        data=output.getvalue(),
                        file_name=f'考勤汇总_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="点击下载合并后的Excel文件"
                    )
                else:
                    st.warning("没有找到有效数据！")
        except Exception as e:
            st.error(f"处理数据时出错: {str(e)}")

# 添加页脚
st.markdown("---")
st.caption("© 2025 考勤信息汇总系统 - 版本 1.0")