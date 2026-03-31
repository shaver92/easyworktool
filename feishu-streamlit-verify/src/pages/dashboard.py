from __future__ import annotations

import streamlit as st

from src.ui.i18n import t


def render_dashboard(materials: list[dict], orders: list[dict], lang: str) -> None:
    st.subheader(t("dashboard", lang))
    available_count = sum(1 for m in materials if m["status"] == "available")
    borrowed_count = sum(1 for o in orders if o["status"] == "borrowed")
    returned_count = sum(1 for o in orders if o["status"] == "returned")
    c1, c2, c3 = st.columns(3)
    c1.metric("可借物资种类" if lang == "zh" else "Available Materials", available_count)
    c2.metric("借用中单据" if lang == "zh" else "Borrowing Orders", borrowed_count)
    c3.metric("已归还单据" if lang == "zh" else "Returned Orders", returned_count)
