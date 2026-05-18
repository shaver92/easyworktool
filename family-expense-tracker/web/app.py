from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path for shared/bot/web imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import streamlit.components.v1 as components

from shared.config import load_config, validate_config
from shared.database import Repository
from web.webhook_handler import patch_streamlit_server, WEBHOOK_PATCH_OK, WEBHOOK_PATCH_ERROR
from web.auth import (
    build_oauth_url,
    resolve_feishu_user,
    resolve_pin_user,
    is_admin,
    hash_pin,
    verify_pin,
    check_rate_limit,
    record_failed_attempt,
    reset_attempts,
)
from web.pages.dashboard import render_dashboard
from web.pages.expense_form import render_expense_form, render_categories, render_budget

st.set_page_config(page_title="家庭记账", page_icon="💰", layout="wide")

# Register Feishu webhook handler on Streamlit's internal Tornado server
# so we can receive Feishu event callbacks without a separate bot deployment.
patch_streamlit_server()

cfg = load_config()
cfg_warnings = validate_config(cfg)

repo = Repository(cfg["app"]["db_path"])
repo.init_schema()

# ---- Auth ----
user = resolve_feishu_user(cfg)

if not user:
    user = resolve_pin_user(cfg)

if not user:
    st.title("💰 家庭记账")
    st.subheader("请登录")

    tab1, tab2 = st.tabs(["飞书登录", "PIN 码登录"])

    with tab1:
        oauth_url = build_oauth_url(cfg)
        if oauth_url:
            st.info("点击下方按钮通过飞书授权登录")
            st.link_button("飞书授权登录", oauth_url, type="primary")

            qp = st.query_params
            if qp.get("code"):
                st.warning("OAuth 登录失败，请检查飞书应用配置。")
        else:
            st.warning("飞书 OAuth 未配置。请在 .env 中设置 FEISHU_APP_ID、FEISHU_APP_SECRET 和 FEISHU_REDIRECT_URI。")

    with tab2:
        all_users = repo.fetch_all("SELECT id, display_name FROM users WHERE auth_method = 'web_pin'")
        if not all_users:
            st.info("还未创建 PIN 用户，请联系管理员。")
        else:
            user_options = {u["display_name"]: u for u in all_users}
            selected_name = st.selectbox("选择身份", list(user_options.keys()))
            pin = st.text_input("输入 4 位 PIN 码", type="password", max_chars=4)

            if st.button("登录", type="primary"):
                selected_user = user_options[selected_name]
                blocked, wait = check_rate_limit(selected_user["id"])
                if blocked:
                    st.error(f"尝试次数过多，请等待 {wait} 秒后再试。")
                else:
                    db_user = repo.fetch_one(
                        "SELECT * FROM users WHERE id = ?",
                        (selected_user["id"],),
                    )
                    if db_user and verify_pin(db_user.get("web_pin_hash"), pin):
                        reset_attempts(selected_user["id"])
                        st.session_state["user"] = dict(db_user)
                        st.rerun()
                    else:
                        record_failed_attempt(selected_user["id"])
                        st.error("PIN 码错误，请重试。")

    if cfg_warnings:
        with st.expander("配置检查", expanded=True):
            for w in cfg_warnings:
                st.warning(w)

    st.stop()

# ---- Authenticated ----

role = "admin" if is_admin(user, cfg) else "member"

# Sidebar
with st.sidebar:
    st.write(f"👤 {user['display_name']} ({role})")

    if "lang" not in st.session_state:
        st.session_state["lang"] = "zh"

    menu = st.radio(
        "导航",
        ["dashboard", "expense_form", "budget", "categories"],
        format_func=lambda x: {
            "dashboard": "📊 消费概览",
            "expense_form": "✏️ 记一笔",
            "budget": "🎯 预算",
            "categories": "🏷️ 类别管理",
        }.get(x, x),
    )

    if st.button("退出登录"):
        st.session_state.pop("user", None)
        st.rerun()

    # Webhook diagnostics
    with st.expander("🔧 Bot 状态"):
        if WEBHOOK_PATCH_OK:
            st.success("Webhook 已注册: /webhook")
            st.caption(f"飞书回调地址: {cfg.get('feishu', {}).get('redirect_uri', 'https://...')}webhook")
        else:
            st.error(f"Webhook 未注册: {WEBHOOK_PATCH_ERROR or '未知错误'}")
            st.caption("飞书事件推送将无法接收，消息记账功能不可用。")

if menu == "dashboard":
    render_dashboard(repo, user, cfg)
elif menu == "expense_form":
    render_expense_form(repo, user)
elif menu == "budget":
    render_budget(repo, user, cfg)
elif menu == "categories":
    render_categories(repo, user)
