from __future__ import annotations

from collections import Counter, defaultdict
import streamlit as st

from src.ui.i18n import t


def render_reports(materials: list[dict], orders: list[dict], lang: str) -> None:
    st.subheader(t("reports", lang))
    c1, c2 = st.columns(2)
    c1.caption("Line / Bar / Stacked Area")
    c2.caption("Read-only analytics page")

    by_status = Counter([o.get("status", "-") for o in orders])
    st.markdown("### " + ("订单状态分布" if lang == "zh" else "Order Status Distribution"))
    st.bar_chart(by_status)

    by_date = Counter([str(o.get("borrow_at", ""))[:10] for o in orders if o.get("borrow_at")])
    if by_date:
        st.markdown("### " + ("借用趋势（折线图）" if lang == "zh" else "Borrow Trend (Line)"))
        st.line_chart(dict(sorted(by_date.items())))

    st.markdown("### " + ("库存对比（堆积图）" if lang == "zh" else "Inventory Comparison (Stacked Area)"))
    stacked = defaultdict(dict)
    for m in materials:
        key = f"{m.get('code', '-')}-{m.get('name', '-')}"
        available = int(m.get("available_qty", 0))
        total = int(m.get("total_qty", 0))
        stacked[key]["available"] = available
        stacked[key]["borrowed"] = max(total - available, 0)
    area_data = {k: {"available": v.get("available", 0), "borrowed": v.get("borrowed", 0)} for k, v in stacked.items()}
    if area_data:
        st.area_chart(area_data)

