from __future__ import annotations

import streamlit as st

from src.ui.i18n import localize_rows, t


def render_materials(materials: list[dict], lang: str) -> None:
    st.subheader(t("materials", lang))
    keyword = st.text_input("搜索物资名称/编码" if lang == "zh" else "Search by name/code")
    rows = materials
    if keyword:
        rows = [m for m in materials if keyword.lower() in m["name"].lower() or keyword.lower() in m["code"].lower()]
    st.dataframe(localize_rows(rows, lang), use_container_width=True, hide_index=True)
