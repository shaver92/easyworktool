# -*- coding: utf-8 -*-


# -------------------------------------------------------------------------------
# Name:         home
# Description:
# Author:       shaver
# Date:         2025/9/26
# -------------------------------------------------------------------------------
import io

import barcode
import img2pdf
import streamlit as st
from barcode.writer import ImageWriter

# 设置页面标题和图标
st.set_page_config(
    page_title="UPC 条形码生成器",
    page_icon="📊",
    layout="centered"
)

# 应用标题和描述
st.title("📊 UPC-A 条形码生成器")
st.markdown("""
这是一个简单的工具，用于生成 UPC-A 条形码并导出为 PDF 文件。
只需输入12位数字，即可生成专业的条形码！
""")

# 创建侧边栏
with st.sidebar:
    st.header("⚙️ 设置")
    dpi = st.slider("分辨率 (DPI)", min_value=150, max_value=600, value=300, step=50)
    module_height = st.slider("条码高度", min_value=10.0, max_value=20.0, value=15.0, step=0.5)
    show_text = st.checkbox("显示数字", value=True)

    st.markdown("---")
    st.info("""
    **使用说明：**
    1. 输入11或12位数字
    2. 点击生成按钮
    3. 预览条形码
    4. 下载PDF文件
    """)

# 主界面
col1, col2 = st.columns([2, 1])

with col1:
    # 输入框
    upc_input = st.text_input(
        "请输入UPC数字:",
        placeholder="例如: 12345678901",
        help="可以输入11位（自动计算校验码）或12位完整数字"
    )

    # 生成按钮
    generate_btn = st.button("🚀 生成条形码", type="primary", use_container_width=True)

with col2:
    # 显示校验码信息
    if upc_input:
        if len(upc_input) == 11:
            try:
                upc_class = barcode.get_barcode_class('upc')
                full_upc = upc_class(upc_input).get_fullcode()
                st.info(f"完整UPC: `{full_upc}`")
            except:
                pass
        elif len(upc_input) == 12:
            st.success("已输入完整12位UPC码")

# 处理生成逻辑
if generate_btn and upc_input:
    try:
        # 验证输入
        if not upc_input.isdigit():
            st.error("❌ 请输入纯数字！")
        elif len(upc_input) not in [11, 12]:
            st.error("❌ 请输入11或12位数字！")
        else:
            with st.spinner("正在生成条形码..."):
                # 生成条形码
                upc_class = barcode.get_barcode_class('upc')
                upc_instance = upc_class(upc_input, writer=ImageWriter())

                # 设置选项
                options = {
                    'module_height': module_height,
                    'write_text': show_text,
                    'text_distance': 5.0,
                    'dpi': dpi,
                    'quiet_zone': 6.0,
                    'background': 'white',
                    'foreground': 'black'
                }

                # 生成PNG到内存
                png_buffer = io.BytesIO()
                upc_instance.write(png_buffer, options=options)
                png_buffer.seek(0)

                # 显示预览
                st.success("✅ 条形码生成成功！")

                col1, col2 = st.columns(2)

                with col1:
                    st.image(png_buffer, caption="条形码预览", use_column_width=True)

                with col2:
                    # 显示条码信息
                    full_code = upc_instance.get_fullcode()
                    st.markdown(f"""
                    **条码信息:**
                    - 类型: UPC-A
                    - 数字: `{full_code}`
                    - 位数: {len(full_code)}
                    - 分辨率: {dpi} DPI
                    """)

                # 生成PDF下载按钮
                st.markdown("---")
                st.subheader("📥 导出选项")

                # 将PNG转换为PDF
                pdf_buffer = io.BytesIO()
                pdf_buffer.write(img2pdf.convert(png_buffer.getvalue()))
                pdf_buffer.seek(0)

                # 创建下载按钮
                st.download_button(
                    label="⬇️ 下载PDF文件",
                    data=pdf_buffer,
                    file_name=f"upc_barcode_{full_code}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

                st.info("💡 提示：PDF文件适合打印和专业使用")

    except Exception as e:
        st.error(f"生成过程中出现错误: {str(e)}")

elif generate_btn:
    st.warning("⚠️ 请输入UPC数字后再点击生成按钮")

# 添加示例和帮助部分
with st.expander("📚 示例和使用帮助"):
    st.markdown("""
    **有效的UPC输入示例:**
    - 11位: `12345678901` (会自动计算第12位校验码)
    - 12位: `123456789012` (完整的UPC-A码)

    **UPC-A 格式说明:**
    - UPC-A 由12位数字组成
    - 最后一位是校验码，用于验证条码的正确性
    - 前6位通常代表厂商编号，后5位代表产品编号

    **常见问题:**
    - Q: 生成的条码能用于商业销售吗？
    - A: 不能。商业用途需要向GS1等机构申请正式的厂商编码。
    - Q: 支持批量生成吗？
    - A: 当前版本支持单个生成，可以多次使用来生成多个条码。
    """)

# 页脚
st.markdown("---")
st.caption("© 2024 UPC条形码生成器 - 基于Python和Streamlit构建")