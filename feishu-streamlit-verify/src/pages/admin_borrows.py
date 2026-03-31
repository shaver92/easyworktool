from __future__ import annotations

import streamlit as st

from src.ui.i18n import localize_rows, t


def render_admin_borrows(user: dict, orders: list[dict], borrow_service, audit_service, focus_order_id: int | None = None) -> None:
    lang = st.session_state.get("lang", "zh")
    st.subheader(t("admin_borrows", lang))
    mode = st.radio("页面模式" if lang == "zh" else "Page Mode", [t("view_only", lang), t("operate_only", lang)], horizontal=True, key="admin_borrow_mode")
    if focus_order_id is not None:
        matched = [o for o in orders if int(o["id"]) == int(focus_order_id)]
        if matched:
            st.info(f"已定位到借用单 #{focus_order_id}")
            st.dataframe(localize_rows(matched, lang), use_container_width=True, hide_index=True)
        else:
            st.warning(f"未找到借用单 #{focus_order_id}")

    if mode == t("view_only", lang):
        st.dataframe(localize_rows(orders, lang), use_container_width=True, hide_index=True)
        return

    st.dataframe(localize_rows(orders, lang), use_container_width=True, hide_index=True)
    pending = [o for o in orders if o["status"] == "pending_approval"]
    if pending:
        st.markdown("### 待审批")
        st.dataframe(pending, use_container_width=True, hide_index=True)
        pending_id = st.selectbox("选择待审批单", [o["id"] for o in pending], key="admin_pending_order_id")
        reject_reason = st.text_input("驳回原因（可选）", key="admin_reject_reason")
        c1, c2 = st.columns(2)
        if c1.button("审批通过"):
            borrow_service.approve_order(int(pending_id), user["open_id"])
            audit_service.log(
                user["open_id"],
                "borrow_approve",
                "borrow_order",
                str(pending_id),
                None,
                {"status": "borrowed"},
            )
            st.success("审批通过，已出库")
            st.rerun()
        if c2.button("驳回申请"):
            borrow_service.reject_order(int(pending_id), user["open_id"], reject_reason)
            audit_service.log(
                user["open_id"],
                "borrow_reject",
                "borrow_order",
                str(pending_id),
                None,
                {"status": "rejected", "reason": reject_reason},
            )
            st.warning("已驳回")
            st.rerun()

    borrowed = [o for o in orders if o["status"] in {"borrowed", "partially_returned"}]
    st.markdown("### 借用中/部分归还")
    if not borrowed:
        st.info("暂无可归还的借用单据")
        return
    borrowed_ids = [o["id"] for o in borrowed]
    default_idx = 0
    if focus_order_id in borrowed_ids:
        default_idx = borrowed_ids.index(focus_order_id)
    order_id = st.selectbox("选择借用单", borrowed_ids, index=default_idx, key="admin_order_id")
    selected = next((o for o in borrowed if int(o["id"]) == int(order_id)), None)
    max_qty = int(selected.get("remaining_qty", 1)) if selected else 1
    qty = st.number_input("本次代归还数量", min_value=1, max_value=max_qty, value=max_qty)
    if st.button("管理员代归还"):
        borrow_service.return_order_partial(int(order_id), user["open_id"], int(qty))
        audit_service.log(
            user["open_id"],
            "admin_force_return",
            "borrow_order",
            str(order_id),
            None,
            {"return_qty": int(qty)},
        )
        st.success("已执行归还")
        st.rerun()
