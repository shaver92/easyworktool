# -*- coding: utf-8 -*-

# -------------------------------------------------------------------------------
# Name:         app
# Description:
# Author:       shaver
# Date:         2025/7/20
# -------------------------------------------------------------------------------

import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import io
import zipfile


def split_pdf_stream(reader, output_ranges):
    """
    reader: PdfReader对象
    output_ranges: 列表，每个元素是(输出文件名, 起始页, 结束页)，页码从1开始
    返回: [(文件名, BytesIO对象)]
    """
    files = []
    for output_name, start, end in output_ranges:
        writer = PdfWriter()
        for i in range(start - 1, end):
            writer.add_page(reader.pages[i])
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        files.append((output_name, output))
    return files


st.title("PDF 拆分工具（按页数分段+自定义文件名+一键下载）")

uploaded_file = st.file_uploader("上传PDF文件", type=["pdf"])

if uploaded_file:
    pdf_reader = PdfReader(uploaded_file)
    total_pages = len(pdf_reader.pages)
    st.write(f"PDF总页数: {total_pages}")

    part_sizes_str = st.text_input(
        "依次输入每个part的页数（用逗号分隔，如：96,192,288,288,192）",
        value=""
    )

    part_ranges = []
    valid = False
    error_msg = ""
    if part_sizes_str:
        try:
            part_sizes = [int(x.strip()) for x in part_sizes_str.split(',') if x.strip()]
            sum_pages = sum(part_sizes)
            if sum_pages != total_pages:
                error_msg = f"所有part页数之和({sum_pages})不等于PDF总页数({total_pages})！"
            else:
                valid = True
                start = 1
                for idx, size in enumerate(part_sizes):
                    end = start + size - 1
                    part_ranges.append((start, end, size))
                    start = end + 1
        except Exception as e:
            error_msg = f"输入格式有误: {e}"

    filenames = []
    if part_sizes_str and valid:
        st.success("页码范围如下（可修改文件名，建议保留页数信息）：")
        for idx, (start, end, size) in enumerate(part_ranges):
            default_name = f"split_{idx + 1}_{start}-{end}_共{size}页.pdf"
            filename = st.text_input(f"Part {idx + 1} 文件名", value=default_name, key=f"filename_{idx}")
            filenames.append(filename)
            st.write(f"页码范围: {start}-{end}，共{size}页")
    elif part_sizes_str:
        st.error(error_msg)

    if valid and filenames and st.button("拆分PDF"):
        try:
            output_ranges = [(filenames[i], part_ranges[i][0], part_ranges[i][1]) for i in range(len(filenames))]
            split_files = split_pdf_stream(pdf_reader, output_ranges)
            st.success(f"拆分完成，共生成 {len(split_files)} 个文件。")
            for filename, filedata in split_files:
                st.download_button(
                    label=f"下载 {filename}",
                    data=filedata,
                    file_name=filename,
                    mime="application/pdf"
                )
            # 打包zip
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zipf:
                for filename, filedata in split_files:
                    filedata.seek(0)
                    zipf.writestr(filename, filedata.read())
            zip_buffer.seek(0)
            st.download_button(
                label="一键下载所有PDF (zip包)",
                data=zip_buffer,
                file_name="all_parts.zip",
                mime="application/zip"
            )
        except Exception as e:
            st.error(f"拆分失败: {e}")
