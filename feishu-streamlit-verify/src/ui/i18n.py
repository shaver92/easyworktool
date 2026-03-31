from __future__ import annotations

import streamlit as st


TEXTS: dict[str, dict[str, str]] = {
    "zh": {
        "app_name": "飞书物资管理系统",
        "language": "语言",
        "chinese": "中文",
        "english": "English",
        "menu": "功能菜单",
        "dashboard": "首页仪表盘",
        "materials": "物资目录",
        "my_borrows": "我的借用",
        "order_detail": "借用单详情",
        "admin_materials": "管理员-物资管理",
        "admin_borrows": "管理员-借用管理",
        "admin_logs": "管理员-日志中心",
        "settings": "系统设置",
        "reports": "统计报表",
        "view_only": "查看列表",
        "operate_only": "新增/操作",
    },
    "en": {
        "app_name": "Feishu Asset Management",
        "language": "Language",
        "chinese": "Chinese",
        "english": "English",
        "menu": "Menu",
        "dashboard": "Dashboard",
        "materials": "Materials",
        "my_borrows": "My Borrows",
        "order_detail": "Order Detail",
        "admin_materials": "Admin - Materials",
        "admin_borrows": "Admin - Borrows",
        "admin_logs": "Admin - Logs",
        "settings": "Settings",
        "reports": "Reports",
        "view_only": "View List",
        "operate_only": "Create/Operate",
    },
}

COLS_ZH = {
    "id": "ID",
    "order_no": "借用单号",
    "status": "状态",
    "applicant_open_id": "申请人OpenID",
    "material_code": "物资编码",
    "material_name": "物资名称",
    "qty": "借用数量",
    "returned_qty": "已归还",
    "remaining_qty": "待归还",
    "due_at": "应还日期",
    "borrow_at": "借出时间",
    "returned_at": "归还时间",
    "note": "备注",
    "code": "物资编码",
    "name": "物资名称",
    "category": "分类",
    "spec": "规格",
    "location": "位置",
    "total_qty": "总库存",
    "available_qty": "可借库存",
    "role": "角色",
    "email": "邮箱",
    "created_at": "创建时间",
    "updated_at": "更新时间",
    "action": "动作",
    "target_type": "目标类型",
    "target_id": "目标ID",
    "receiver_open_id": "接收人OpenID",
    "notify_type": "通知类型",
    "retry_count": "重试次数",
    "last_error": "最后错误",
    "sent_at": "发送时间",
}

COLS_EN = {
    "id": "ID",
    "order_no": "Order No",
    "status": "Status",
    "applicant_open_id": "Applicant OpenID",
    "material_code": "Material Code",
    "material_name": "Material Name",
    "qty": "Qty",
    "returned_qty": "Returned",
    "remaining_qty": "Remaining",
    "due_at": "Due Date",
    "borrow_at": "Borrowed At",
    "returned_at": "Returned At",
    "note": "Note",
    "code": "Code",
    "name": "Name",
    "category": "Category",
    "spec": "Spec",
    "location": "Location",
    "total_qty": "Total Qty",
    "available_qty": "Available Qty",
    "role": "Role",
    "email": "Email",
    "created_at": "Created At",
    "updated_at": "Updated At",
    "action": "Action",
    "target_type": "Target Type",
    "target_id": "Target ID",
    "receiver_open_id": "Receiver OpenID",
    "notify_type": "Notify Type",
    "retry_count": "Retry Count",
    "last_error": "Last Error",
    "sent_at": "Sent At",
}

STATUS_ZH = {
    "available": "可借",
    "maintenance": "维护中",
    "retired": "停用",
    "off_shelf": "下架",
    "pending_approval": "待审批",
    "rejected": "已驳回",
    "borrowed": "借用中",
    "partially_returned": "部分归还",
    "returned": "已归还",
    "pending": "待发送",
    "sent": "已发送",
}

STATUS_EN = {
    "available": "Available",
    "maintenance": "Maintenance",
    "retired": "Retired",
    "off_shelf": "Off Shelf",
    "pending_approval": "Pending Approval",
    "rejected": "Rejected",
    "borrowed": "Borrowed",
    "partially_returned": "Partially Returned",
    "returned": "Returned",
    "pending": "Pending",
    "sent": "Sent",
}


def t(key: str, lang: str) -> str:
    return TEXTS.get(lang, TEXTS["zh"]).get(key, key)


def normalize_lang() -> str:
    value = st.session_state.get("lang", "zh")
    return "en" if value == "en" else "zh"


def localize_rows(rows: list[dict], lang: str) -> list[dict]:
    col_map = COLS_EN if lang == "en" else COLS_ZH
    status_map = STATUS_EN if lang == "en" else STATUS_ZH
    localized: list[dict] = []
    for row in rows:
        item: dict = {}
        for k, v in row.items():
            nk = col_map.get(k, k)
            nv = status_map.get(v, v) if isinstance(v, str) else v
            item[nk] = nv
        localized.append(item)
    return localized

