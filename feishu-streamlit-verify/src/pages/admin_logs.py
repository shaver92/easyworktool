from __future__ import annotations

import streamlit as st


def render_admin_logs(audit_logs: list[dict], notifications: list[dict], notify_service) -> None:
    st.subheader("管理员 - 日志中心")
    c1, c2 = st.columns(2)
    if c1.button("手动补发待发送通知"):
        notify_service.dispatch_pending()
        st.success("补发任务已执行")
        st.rerun()
    if c2.button("刷新日志"):
        st.rerun()
    tab1, tab2 = st.tabs(["审计日志", "通知日志"])
    with tab1:
        st.dataframe(audit_logs, use_container_width=True, hide_index=True)
    with tab2:
        st.dataframe(notifications, use_container_width=True, hide_index=True)
