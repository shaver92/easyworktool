from __future__ import annotations

import streamlit as st

from src.ui.i18n import localize_rows, t


def render_admin_logs(audit_logs: list[dict], notifications: list[dict], notify_service) -> None:
    lang = st.session_state.get("lang", "zh")
    st.subheader(t("admin_logs", lang))
    mode = st.radio("页面模式" if lang == "zh" else "Page Mode", [t("view_only", lang), t("operate_only", lang)], horizontal=True, key="admin_log_mode")
    if mode == t("operate_only", lang):
        c1, c2 = st.columns(2)
        if c1.button("手动补发待发送通知" if lang == "zh" else "Retry Pending Notifications"):
            notify_service.dispatch_pending()
            st.success("补发任务已执行" if lang == "zh" else "Retry done.")
            st.rerun()
        if c2.button("刷新日志" if lang == "zh" else "Refresh Logs"):
            st.rerun()
        return
    tab1, tab2 = st.tabs(["审计日志" if lang == "zh" else "Audit Logs", "通知日志" if lang == "zh" else "Notification Logs"])
    with tab1:
        st.dataframe(localize_rows(audit_logs, lang), use_container_width=True, hide_index=True)
    with tab2:
        st.dataframe(localize_rows(notifications, lang), use_container_width=True, hide_index=True)
