from __future__ import annotations

from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from src.auth.feishu_auth import build_oauth_login_url, resolve_user
from src.auth.rbac import is_admin
from src.config import load_config, validate_config
from src.db.repository import Repository
from src.pages.admin_borrows import render_admin_borrows
from src.pages.admin_logs import render_admin_logs
from src.pages.admin_materials import render_admin_materials
from src.pages.dashboard import render_dashboard
from src.pages.materials import render_materials
from src.pages.my_borrows import render_my_borrows
from src.pages.order_detail import render_order_detail
from src.pages.reports import render_reports
from src.pages.settings import render_settings
from src.services.audit_service import AuditService
from src.services.borrow_service import BorrowService
from src.services.material_service import MaterialService
from src.services.notify_service import NotifyService
from src.services.scheduler import start_scheduler
from src.ui.i18n import normalize_lang, t
from src.ui.theme import apply_theme


st.set_page_config(page_title="飞书物资管理系统", page_icon="📦", layout="wide")
apply_theme()

cfg = load_config()
cfg_warnings = validate_config(cfg)
repo = Repository(cfg["app"]["db_path"])
repo.init_schema()

material_service = MaterialService(repo)
borrow_service = BorrowService(repo, require_approval=cfg["app"].get("require_borrow_approval", False))
audit_service = AuditService(repo)
notify_service = NotifyService(repo, cfg)
if "scheduler_started" not in st.session_state:
    st.session_state["scheduler"] = start_scheduler(borrow_service, notify_service, cfg)
    st.session_state["scheduler_started"] = True

material_service.seed_demo_if_empty()

user = resolve_user(cfg)
role = "admin" if is_admin(user, cfg) else "user"
repo.execute(
    """
    INSERT INTO users(open_id, name, email, role)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(open_id) DO UPDATE SET
        name = excluded.name,
        email = excluded.email,
        role = excluded.role,
        updated_at = CURRENT_TIMESTAMP
    """,
    (user["open_id"], user["name"], user.get("email", ""), role),
)

materials = material_service.list_materials(include_off_shelf=(role == "admin"))
my_orders = borrow_service.list_orders(applicant_open_id=user["open_id"])
all_orders = borrow_service.list_orders()
notify_service.dispatch_pending()

st.title(cfg["app"]["name"])
if "lang" not in st.session_state:
    st.session_state["lang"] = "zh"
lang_options = {"zh": t("chinese", "zh"), "en": t("english", "zh")}
selected_lang = st.sidebar.selectbox(t("language", "zh"), list(lang_options.keys()), format_func=lambda x: lang_options[x])
st.session_state["lang"] = selected_lang
lang = normalize_lang()
st.caption(f"当前用户：{user['name']} ({user['open_id']}) | 角色：{role} | 来源：{user.get('source', 'unknown')}")
if user.get("source") == "demo":
    st.warning("当前为演示身份。可通过 URL 传入 open_id，或在飞书工作台通过 OAuth 回调参数 code 登录。")
    qp = st.query_params
    oauth_url = build_oauth_login_url(cfg)
    should_auto_oauth = (
        bool(oauth_url)
        and not qp.get("code")
        and not qp.get("open_id")
        and not qp.get("user_access_token")
        and not qp.get("no_auto_oauth")
        and not st.session_state.get("auto_oauth_triggered", False)
    )
    if should_auto_oauth:
        st.session_state["auto_oauth_triggered"] = True
        st.info("正在自动跳转飞书授权页面...")
        components.html(
            f"""
            <script>
            const target = {oauth_url!r};
            try {{
              window.top.location.replace(target);
            }} catch (e) {{
              window.location.replace(target);
            }}
            </script>
            """,
            height=0,
        )
        st.link_button("若未自动跳转，请点此授权", oauth_url, type="secondary")
        st.stop()
    if oauth_url:
        st.link_button("使用飞书授权登录（获取真实用户）", oauth_url, type="primary")
    with st.expander("登录诊断信息", expanded=False):
        qp_debug = dict(qp)
        st.write("当前 URL 查询参数：", qp_debug)
        if qp_debug.get("code"):
            st.write("检测到 code 已回传，但用户仍为 demo，通常是 code 换 token 或用户信息请求失败。")
            auth_debug = st.session_state.get("auth_debug", {})
            if auth_debug:
                st.write("OAuth 调用明细：", auth_debug)
        else:
            st.write("未检测到 code，通常说明当前进入的是应用主页直达链接，未经过 OAuth 授权页。")
if cfg_warnings:
    with st.expander("配置检查告警", expanded=True):
        for w in cfg_warnings:
            st.warning(w)
st.write(("当前服务器时间：" if lang == "zh" else "Server time:"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

menu = [
    ("dashboard", t("dashboard", lang)),
    ("materials", t("materials", lang)),
    ("my_borrows", t("my_borrows", lang)),
    ("order_detail", t("order_detail", lang)),
    ("reports", t("reports", lang)),
]
if role == "admin":
    menu += [
        ("admin_materials", t("admin_materials", lang)),
        ("admin_borrows", t("admin_borrows", lang)),
        ("admin_logs", t("admin_logs", lang)),
        ("settings", t("settings", lang)),
    ]
qp = st.query_params
focus_order_id = qp.get("order_id")
default_page = qp.get("page")
menu_ids = [m[0] for m in menu]
menu_labels = {k: v for k, v in menu}
default_index = menu_ids.index(default_page) if default_page in menu_ids else 0
selected_page = st.sidebar.radio(t("menu", lang), menu_ids, index=default_index, format_func=lambda x: menu_labels[x])

if selected_page == "dashboard":
    render_dashboard(materials, all_orders, lang)
elif selected_page == "materials":
    render_materials(materials, lang)
elif selected_page == "my_borrows":
    focus_id = int(focus_order_id) if focus_order_id and str(focus_order_id).isdigit() else None
    render_my_borrows(user, materials, my_orders, borrow_service, audit_service, focus_id)
elif selected_page == "order_detail":
    focus_id = int(focus_order_id) if focus_order_id and str(focus_order_id).isdigit() else None
    detail = borrow_service.get_order_detail(focus_id) if focus_id else None
    render_order_detail(
        user=user,
        role=role,
        order_detail=detail,
        order_audit_logs=audit_service.list_logs_by_target("borrow_order", str(focus_id), 300) if focus_id else [],
        order_notifications=notify_service.list_notifications_by_order(focus_id, 300) if focus_id else [],
        borrow_service=borrow_service,
        audit_service=audit_service,
        notify_service=notify_service,
    )
elif selected_page == "reports":
    render_reports(materials, all_orders, lang)
elif selected_page == "admin_materials":
    render_admin_materials(user, materials, material_service, audit_service, repo)
elif selected_page == "admin_borrows":
    focus_id = int(focus_order_id) if focus_order_id and str(focus_order_id).isdigit() else None
    render_admin_borrows(user, all_orders, borrow_service, audit_service, focus_id)
elif selected_page == "admin_logs":
    render_admin_logs(audit_service.list_logs(), notify_service.list_notifications(), notify_service)
elif selected_page == "settings":
    render_settings(cfg, user)
