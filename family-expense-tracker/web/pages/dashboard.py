from __future__ import annotations

import streamlit as st

from shared.database import Repository
from web import charts


def render_dashboard(repo: Repository, user: dict, cfg: dict):
    lang = st.session_state.get("lang", "zh")

    st.header("📊 消费概览" if lang == "zh" else "Spending Overview")

    # Period selector
    period = st.radio(
        "统计周期" if lang == "zh" else "Period",
        ["week", "month", "year"],
        horizontal=True,
        format_func={"week": "本周", "month": "本月", "year": "今年"}.get if lang == "zh" else str.title,
    )

    if period == "week":
        summary = charts.weekly_summary(repo)
    elif period == "month":
        summary = charts.monthly_summary(repo, 2026, 5)
    else:
        summary = charts.yearly_summary(repo, 2026)

    # KPI cards
    if summary["count"] == 0:
        st.info("还没有消费记录，去飞书或网页录入一笔吧！" if lang == "zh" else "No expenses yet.")
    else:
        charts.render_summary_cards(summary)

        st.subheader("分类占比" if lang == "zh" else "By Category")
        charts.render_pie_chart(summary["categories"])

        if period == "year":
            st.subheader("月度趋势" if lang == "zh" else "Monthly Trend")
        else:
            st.subheader("每日趋势" if lang == "zh" else "Daily Trend")

        if period == "year":
            charts.render_trend_chart(summary.get("monthly", []), title="月度趋势")
        else:
            charts.render_trend_chart(summary.get("daily", []), title="每日趋势")

        # Budget warning
        now_month = "2026-05"
        budget = charts.budget_status(repo, user["id"], now_month)
        if budget and budget["over_threshold"]:
            ratio_pct = budget["ratio"] * 100
            if budget["over_budget"]:
                st.error(f"⚠️ 本月预算已超支！已花 ¥{budget['spent']:,.2f} / 预算 ¥{budget['budget_amount']:,.2f} ({ratio_pct:.0f}%)")
            else:
                st.warning(f"🔶 本月预算已使用 {ratio_pct:.0f}%（¥{budget['spent']:,.2f} / ¥{budget['budget_amount']:,.2f}）")

    # Recent entries
    st.subheader("最近记录" if lang == "zh" else "Recent Entries")
    recent = repo.fetch_all("""
        SELECT e.amount, c.icon, c.name AS category, e.note, e.recorded_at, u.display_name
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        JOIN users u ON e.user_id = u.id
        ORDER BY e.recorded_at DESC
        LIMIT 20
    """)

    if not recent:
        st.info("还没有消费记录")
    else:
        for r in recent:
            st.write(f"**{r['icon']} {r['amount']:.2f}** — {r['display_name']} | {r['category']} | {r.get('note', '')} | _{r['recorded_at']}_")
