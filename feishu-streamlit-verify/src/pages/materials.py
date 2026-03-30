from __future__ import annotations

import streamlit as st


def render_materials(materials: list[dict]) -> None:
    st.subheader("物资目录")
    keyword = st.text_input("搜索物资名称/编码")
    rows = materials
    if keyword:
        rows = [m for m in materials if keyword.lower() in m["name"].lower() or keyword.lower() in m["code"].lower()]
    st.dataframe(rows, use_container_width=True, hide_index=True)
