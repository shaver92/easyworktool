from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from shared.database import Repository


def weekly_summary(repo: Repository, timezone: str = "Asia/Shanghai") -> dict:
    """Get weekly expense summary grouped by category."""
    row = repo.fetch_one("""
        SELECT COALESCE(SUM(amount), 0) AS total,
               COUNT(*) AS count
        FROM expenses
        WHERE recorded_at >= date('now', 'weekday 0', '-6 days', 'localtime')
          AND type = 'expense'
    """)
    total = row["total"] if row else 0
    count = row["count"] if row else 0

    categories = repo.fetch_all("""
        SELECT c.name, c.icon, COALESCE(SUM(e.amount), 0) AS subtotal
        FROM categories c
        LEFT JOIN expenses e ON c.id = e.category_id
            AND e.recorded_at >= date('now', 'weekday 0', '-6 days', 'localtime')
            AND e.type = 'expense'
        GROUP BY c.id
        ORDER BY subtotal DESC
    """)

    daily = repo.fetch_all("""
        SELECT date(recorded_at) AS day, COALESCE(SUM(amount), 0) AS total
        FROM expenses
        WHERE recorded_at >= date('now', 'weekday 0', '-6 days', 'localtime')
          AND type = 'expense'
        GROUP BY day
        ORDER BY day
    """)

    return {"total": total, "count": count, "categories": categories, "daily": daily}


def monthly_summary(repo: Repository, year: int, month: int) -> dict:
    """Get monthly expense summary grouped by category."""
    ym = f"{year}-{month:02d}"
    row = repo.fetch_one("""
        SELECT COALESCE(SUM(amount), 0) AS total,
               COUNT(*) AS count
        FROM expenses
        WHERE strftime('%Y-%m', recorded_at) = ?
          AND type = 'expense'
    """, (ym,))
    total = row["total"] if row else 0
    count = row["count"] if row else 0

    categories = repo.fetch_all("""
        SELECT c.name, c.icon, COALESCE(SUM(e.amount), 0) AS subtotal
        FROM categories c
        LEFT JOIN expenses e ON c.id = e.category_id
            AND strftime('%Y-%m', e.recorded_at) = ?
            AND e.type = 'expense'
        GROUP BY c.id
        ORDER BY subtotal DESC
    """, (ym,))

    daily = repo.fetch_all("""
        SELECT date(recorded_at) AS day, COALESCE(SUM(amount), 0) AS total
        FROM expenses
        WHERE strftime('%Y-%m', recorded_at) = ?
          AND type = 'expense'
        GROUP BY day
        ORDER BY day
    """, (ym,))

    return {"total": total, "count": count, "categories": categories, "daily": daily}


def yearly_summary(repo: Repository, year: int) -> dict:
    """Get yearly expense summary grouped by month and category."""
    row = repo.fetch_one("""
        SELECT COALESCE(SUM(amount), 0) AS total,
               COUNT(*) AS count
        FROM expenses
        WHERE strftime('%Y', recorded_at) = ?
          AND type = 'expense'
    """, (str(year),))
    total = row["total"] if row else 0
    count = row["count"] if row else 0

    categories = repo.fetch_all("""
        SELECT c.name, c.icon, COALESCE(SUM(e.amount), 0) AS subtotal
        FROM categories c
        LEFT JOIN expenses e ON c.id = e.category_id
            AND strftime('%Y', e.recorded_at) = ?
            AND e.type = 'expense'
        GROUP BY c.id
        ORDER BY subtotal DESC
    """, (str(year),))

    monthly = repo.fetch_all("""
        SELECT strftime('%m', recorded_at) AS month, COALESCE(SUM(amount), 0) AS total
        FROM expenses
        WHERE strftime('%Y', recorded_at) = ?
          AND type = 'expense'
        GROUP BY month
        ORDER BY month
    """, (str(year),))

    return {"total": total, "count": count, "categories": categories, "monthly": monthly}


def budget_status(repo: Repository, user_id: int, month: str) -> dict | None:
    """Get budget status for a user in a given month. Returns None if no budget set."""
    budget = repo.fetch_one(
        "SELECT * FROM budgets WHERE user_id = ? AND month = ? AND category_id IS NULL",
        (user_id, month),
    )
    if not budget:
        return None

    spent = repo.fetch_scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ? AND strftime('%Y-%m', recorded_at) = ? AND type = 'expense'",
        (user_id, month),
    ) or 0

    ratio = spent / budget["amount"]
    over_threshold = ratio >= budget["warn_threshold"]
    over_budget = ratio >= 1.0

    return {
        "budget_amount": budget["amount"],
        "spent": spent,
        "ratio": ratio,
        "over_threshold": over_threshold,
        "over_budget": over_budget,
        "warn_threshold": budget["warn_threshold"],
    }


def render_pie_chart(categories: list[dict], title: str = "分类占比"):
    """Render a Plotly pie chart for category breakdown."""
    if not categories or all(c["subtotal"] == 0 for c in categories):
        st.info("暂无消费数据")
        return

    df = pd.DataFrame([{"类别": f"{c['icon']} {c['name']}", "金额": c["subtotal"]} for c in categories if c["subtotal"] > 0])
    if df.empty:
        st.info("暂无消费数据")
        return

    fig = px.pie(df, values="金额", names="类别", title=title, hole=0.4)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)


def render_trend_chart(daily: list[dict], title: str = "每日趋势"):
    """Render a Plotly bar chart for daily spending trend."""
    if not daily:
        st.info("暂无消费数据")
        return

    df = pd.DataFrame([{"日期": d["day"], "金额": d["total"]} for d in daily])
    if df.empty:
        st.info("暂无消费数据")
        return

    fig = px.bar(df, x="日期", y="金额", title=title)
    fig.update_layout(bargap=0.2)
    st.plotly_chart(fig, use_container_width=True)


def render_summary_cards(summary: dict):
    """Render KPI summary cards."""
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总支出", f"¥{summary['total']:,.2f}")
    with col2:
        st.metric("记账笔数", str(summary["count"]))
    with col3:
        top_cat = summary["categories"][0]["name"] if summary["categories"] else "—"
        st.metric("最多类别", f"{summary['categories'][0]['icon'] if summary['categories'] else ''} {top_cat}")
