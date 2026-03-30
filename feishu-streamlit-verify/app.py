from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.auth.feishu_auth import resolve_user
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
from src.pages.settings import render_settings
from src.services.audit_service import AuditService
from src.services.borrow_service import BorrowService
from src.services.material_service import MaterialService
from src.services.notify_service import NotifyService
from src.services.scheduler import start_scheduler


st.set_page_config(page_title="飞书物资管理系统", page_icon="📦", layout="wide")

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
st.caption(f"当前用户：{user['name']} ({user['open_id']}) | 角色：{role} | 来源：{user.get('source', 'unknown')}")
if user.get("source") == "demo":
    st.warning("当前为演示身份。可通过 URL 传入 open_id，或在飞书工作台通过 OAuth 回调参数 code 登录。")
if cfg_warnings:
    with st.expander("配置检查告警", expanded=True):
        for w in cfg_warnings:
            st.warning(w)
st.write("当前服务器时间：", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

menu = ["首页", "物资目录", "我的借用", "借用单详情"]
if role == "admin":
    menu += ["管理员-物资管理", "管理员-借用管理", "管理员-日志中心", "系统设置"]
qp = st.query_params
focus_order_id = qp.get("order_id")
default_page = qp.get("page")
default_index = menu.index(default_page) if default_page in menu else 0
selected_page = st.sidebar.radio("功能菜单", menu, index=default_index)

if selected_page == "首页":
    render_dashboard(materials, all_orders)
elif selected_page == "物资目录":
    render_materials(materials)
elif selected_page == "我的借用":
    focus_id = int(focus_order_id) if focus_order_id and str(focus_order_id).isdigit() else None
    render_my_borrows(user, materials, my_orders, borrow_service, audit_service, focus_id)
elif selected_page == "借用单详情":
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
elif selected_page == "管理员-物资管理":
    render_admin_materials(user, materials, material_service, audit_service, repo)
elif selected_page == "管理员-借用管理":
    focus_id = int(focus_order_id) if focus_order_id and str(focus_order_id).isdigit() else None
    render_admin_borrows(user, all_orders, borrow_service, audit_service, focus_id)
elif selected_page == "管理员-日志中心":
    render_admin_logs(audit_service.list_logs(), notify_service.list_notifications(), notify_service)
elif selected_page == "系统设置":
    render_settings(cfg, user)
