from __future__ import annotations

import streamlit as st

from shared.database import Repository


def render_expense_form(repo: Repository, user: dict):
    """Simple web expense entry form (fallback for non-Feishu users)."""
    lang = st.session_state.get("lang", "zh")

    st.header("记一笔" if lang == "zh" else "Record Expense")

    categories = repo.fetch_all("SELECT id, name, icon FROM categories ORDER BY is_system DESC, name")
    cat_options = {f"{c['icon']} {c['name']}": c["id"] for c in categories}

    with st.form("expense_form", clear_on_submit=True):
        col1, col2 = st.columns([1, 1])
        with col1:
            amount = st.number_input("金额" if lang == "zh" else "Amount", min_value=0.01, step=0.01, format="%.2f")
        with col2:
            cat_choice = st.selectbox("类别", list(cat_options.keys()))
        note = st.text_input("备注（可选）", placeholder="中午请客...")
        submitted = st.form_submit_button("保存" if lang == "zh" else "Save")

        if submitted:
            category_id = cat_options[cat_choice]
            try:
                repo.execute(
                    "INSERT INTO expenses (user_id, category_id, amount, type, note, source) VALUES (?, ?, ?, 'expense', ?, 'web')",
                    (user["id"], category_id, amount, note),
                )
                st.success(f"已记录：¥{amount:.2f}")
            except Exception as exc:
                st.error(f"保存失败：{exc}")


def render_categories(repo: Repository, user: dict):
    """Category management page."""
    lang = st.session_state.get("lang", "zh")

    st.header("费用类别管理" if lang == "zh" else "Categories")

    categories = repo.fetch_all("SELECT * FROM categories ORDER BY is_system DESC, name")
    for cat in categories:
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            st.write(cat["icon"])
        with col2:
            st.write(cat["name"])
        with col3:
            if not cat["is_system"]:
                if st.button("删除", key=f"del_cat_{cat['id']}"):
                    repo.execute("DELETE FROM categories WHERE id = ? AND is_system = 0", (cat["id"],))
                    st.rerun()
            else:
                st.caption("预设")

    with st.form("add_category", clear_on_submit=True):
        col1, col2 = st.columns([1, 3])
        with col1:
            icon = st.text_input("图标", value="📌", max_chars=2)
        with col2:
            name = st.text_input("类别名称")
        if st.form_submit_button("添加"):
            if name.strip():
                repo.execute(
                    "INSERT OR IGNORE INTO categories (name, icon, created_by) VALUES (?, ?, ?)",
                    (name.strip(), icon, user["id"]),
                )
                st.rerun()


def render_budget(repo: Repository, user: dict, cfg: dict):
    """Budget settings page."""
    lang = st.session_state.get("lang", "zh")

    st.header("预算设置" if lang == "zh" else "Budget Settings")

    from web.charts import budget_status

    current_month = "2026-05"
    months = ["2026-05", "2026-06", "2026-07", "2026-08"]
    month_labels = {
        "2026-05": "2026年5月",
        "2026-06": "2026年6月",
        "2026-07": "2026年7月",
        "2026-08": "2026年8月",
    }

    # Show existing budgets
    existing = repo.fetch_all(
        "SELECT * FROM budgets WHERE user_id = ? ORDER BY month DESC",
        (user["id"],),
    )
    if existing:
        for b in existing:
            status = budget_status(repo, user["id"], b["month"])
            ratio = status["ratio"] * 100 if status else 0
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.write(f"**{b['month']}**")
            with col2:
                st.write(f"¥{b['amount']:,.2f} / 提醒线 {b['warn_threshold']*100:.0f}%")
            with col3:
                if ratio >= 100:
                    st.error(f"{ratio:.0f}%")
                elif ratio >= b["warn_threshold"] * 100:
                    st.warning(f"{ratio:.0f}%")
                else:
                    st.write(f"{ratio:.0f}%")

    # Set/update budget
    with st.form("budget_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_month = st.selectbox("月份" if lang == "zh" else "Month", months, format_func=lambda m: month_labels.get(m, m))
        with col2:
            amount = st.number_input("月度预算" if lang == "zh" else "Monthly Budget", min_value=100.0, step=100.0, value=5000.0, format="%.0f")
        with col3:
            threshold = st.slider("预警线" if lang == "zh" else "Warn at", min_value=50, max_value=100, value=80, step=5) / 100.0

        if st.form_submit_button("保存" if lang == "zh" else "Save"):
            repo.execute(
                """INSERT OR REPLACE INTO budgets (user_id, category_id, amount, month, warn_threshold)
                   VALUES (?, NULL, ?, ?, ?)""",
                (user["id"], amount, selected_month, threshold),
            )
            st.success("已保存")
            st.rerun()
