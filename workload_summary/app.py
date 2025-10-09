# -*- coding: utf-8 -*-
import streamlit as st
import time
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title="工时统计系统", layout="wide")

# 页面标题
st.title("工时统计系统")
st.markdown("---")

# 参数配置表单
with st.form(key='config_form'):
    st.subheader("API配置")
    col1, col2, col3 = st.columns(3)
    with col1:
        base_url = st.text_input("Base URL", value="https://tp-devops.crv.com.cn/open")
    with col2:
        client_id = st.text_input("Client ID", value="qnIIzSQmLKHt")
    with col3:
        client_secret = st.text_input("Client Secret", value="iIYrfmcHcDRZLjJWBrgXnaUc")

    st.subheader("时间范围")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", value=datetime(2025, 1, 1))
    with col2:
        end_date = st.date_input("结束日期", value=datetime(2025, 7, 31))

    st.subheader("用户列表文件")
    uploaded_file = st.file_uploader("上传user.txt文件", type=['txt'])

    submit_button = st.form_submit_button("开始处理")

# 处理逻辑
if submit_button and uploaded_file is not None:
    # 转换日期为时间戳
    start_at = int(time.mktime(start_date.timetuple()))
    end_at = int(time.mktime(end_date.timetuple()))

    # 获取访问令牌
    with st.spinner("正在获取访问令牌..."):
        token_url = f"{base_url}/v1/auth/token?grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}"
        try:
            token_response = requests.get(token_url)
            if token_response.status_code == 200:
                access_token = token_response.json().get('access_token')
                st.success("令牌获取成功!")
            else:
                st.error(f"令牌获取失败: {token_response.status_code} - {token_response.text}")
                st.stop()
        except Exception as e:
            st.error(f"令牌请求异常: {str(e)}")
            st.stop()

    # 处理用户数据
    work_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 读取上传的文件内容
    file_contents = uploaded_file.getvalue().decode('utf-8').splitlines()
    total_users = len(file_contents)

    for i, line in enumerate(file_contents):
        if not line.strip():
            continue

        try:
            user_id, ldap_name, name = line.strip().split('\t')
        except ValueError:
            st.warning(f"跳过格式错误的行: {line}")
            continue

        status_text.text(f"正在处理用户 {name} ({i + 1}/{total_users})")
        progress_bar.progress((i + 1) / total_users)

        # 查询当前人员工时
        page_index = 0
        while True:
            url = f"{base_url}/v1/workloads?report_by_id={user_id}&start_at={start_at}&end_at={end_at}&access_token={access_token}&page_index={page_index}&page_size=99"

            try:
                url_response = requests.get(url)
                if url_response.status_code != 200:
                    st.warning(f"用户 {name} 第 {page_index + 1} 页数据获取失败: {url_response.status_code}")
                    break

                values = url_response.json().get('values')
                if len(values) == 0:
                    break

                for value in values:
                    report_at = value.get('report_at')
                    report_at = pd.to_datetime(report_at, unit='s').strftime('%Y-%m-%d')
                    duration = value.get('duration')
                    description = value.get('description')

                    type_data = value.get('type')
                    type_name = type_data.get('name') if type_data else None

                    principal = value.get('principal')
                    title = principal.get('title') if principal else None
                    work_item_id = principal.get('id') if principal else None
                    principal_identifier = principal.get('identifier') if principal else None

                    time.sleep(0.2)

                    if work_item_id:
                        work_items_url = f"{base_url}/v1/project/work_items/{work_item_id}?access_token={access_token}"
                        work_items_response = requests.get(work_items_url)
                        work_item_value = work_items_response.json()

                        project = work_item_value.get('project')
                        project_name = project.get('name') if project else ''
                        project_identifier = project.get('identifier') if project else ''

                    work_data.append({
                        'report_at': report_at,
                        'user_id': user_id,
                        'name': name,
                        "principal_identifier": principal_identifier,
                        'title': title,
                        'description': description,
                        'duration': duration,
                        'type_name': type_name,
                        'project_name': project_name,
                        'project_identifier': project_identifier
                    })

                page_index += 1
            except Exception as e:
                st.warning(f"处理用户 {name} 第 {page_index + 1} 页时出错: {str(e)}")
                break

    # 生成结果DataFrame
    if work_data:
        df = pd.DataFrame(work_data, columns=[
            "report_at", "user_id", "name", "principal_identifier",
            "title", "description", "duration", "type_name",
            "project_name", "project_identifier"
        ])

        # 显示结果预览
        st.subheader("处理结果预览")
        st.dataframe(df.head())

        # 提供下载
        st.subheader("结果下载")
        excel_file = f"workload_summary_data_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        towrite = io.BytesIO()
        df.to_excel(towrite, index=False, engine='openpyxl')
        towrite.seek(0)

        st.download_button(
            label="下载Excel文件",
            data=towrite,
            file_name=excel_file,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.success("处理完成!")
    else:
        st.warning("未获取到任何工时数据")

elif submit_button and uploaded_file is None:
    st.error("请上传用户列表文件!")