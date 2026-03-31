from __future__ import annotations

import streamlit as st

from src.ui.i18n import localize_rows


def render_order_detail(
    user: dict,
    role: str,
    order_detail: dict | None,
    order_audit_logs: list[dict],
    order_notifications: list[dict],
    borrow_service,
    audit_service,
    notify_service,
) -> None:
    lang = st.session_state.get("lang", "zh")
    st.subheader("借用单详情" if lang == "zh" else "Order Detail")
    if not order_detail:
        st.info("请选择或传入有效的借用单 ID")
        return
    if role != "admin" and order_detail["applicant_open_id"] != user["open_id"]:
        st.error("你无权查看此借用单详情")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("借用单号", order_detail["order_no"])
    c2.metric("状态", order_detail["status"])
    c3.metric("应还日期", order_detail["due_at"])
    st.write(
        {
            "申请人": order_detail["applicant_open_id"],
            "物资": f"{order_detail['material_code']} - {order_detail['material_name']}",
            "数量": order_detail["qty"],
            "已归还": order_detail.get("returned_qty", 0),
            "待归还": order_detail.get("remaining_qty", order_detail["qty"]),
            "借出时间": order_detail["borrow_at"],
            "归还时间": order_detail["returned_at"] or "-",
            "备注": order_detail["note"] or "-",
        }
    )

    remaining_qty = int(order_detail.get("remaining_qty", 0))
    if role == "admin" and order_detail["status"] == "pending_approval":
        reject_reason = st.text_input("驳回原因（可选）", key=f"detail_reject_reason_{order_detail['id']}")
        c1, c2 = st.columns(2)
        if c1.button("详情页审批通过"):
            borrow_service.approve_order(int(order_detail["id"]), user["open_id"])
            audit_service.log(
                user["open_id"],
                "borrow_approve_from_detail",
                "borrow_order",
                str(order_detail["id"]),
                None,
                {"status": "borrowed"},
            )
            st.success("审批通过，已出库")
            st.rerun()
        if c2.button("详情页驳回"):
            borrow_service.reject_order(int(order_detail["id"]), user["open_id"], reject_reason)
            audit_service.log(
                user["open_id"],
                "borrow_reject_from_detail",
                "borrow_order",
                str(order_detail["id"]),
                None,
                {"status": "rejected", "reason": reject_reason},
            )
            st.warning("已驳回")
            st.rerun()

    if order_detail["status"] in {"borrowed", "partially_returned"} and remaining_qty > 0:
        return_qty = st.number_input("本次归还数量", min_value=1, max_value=remaining_qty, value=remaining_qty)
        if st.button("在详情页执行归还", type="primary"):
            borrow_service.return_order_partial(int(order_detail["id"]), user["open_id"], int(return_qty))
            audit_service.log(
                user["open_id"],
                "borrow_return_from_detail",
                "borrow_order",
                str(order_detail["id"]),
                None,
                {"return_qty": int(return_qty)},
            )
            st.success("归还成功")
            st.rerun()
    if role == "admin" and order_detail["status"] in {"borrowed", "partially_returned"}:
        if st.button("管理员催还一次"):
            notify_service.enqueue_manual_notice(order_detail, user["open_id"])
            notify_service.dispatch_pending()
            audit_service.log(
                user["open_id"],
                "manual_remind_send",
                "borrow_order",
                str(order_detail["id"]),
                None,
                {"notify_type": "manual_remind"},
            )
            st.success("催还提醒已发送")
            st.rerun()

    t1, t2 = st.tabs(["审计轨迹" if lang == "zh" else "Audit Trail", "通知轨迹" if lang == "zh" else "Notify Trail"])
    with t1:
        st.dataframe(localize_rows(order_audit_logs, lang), use_container_width=True, hide_index=True)
    with t2:
        st.dataframe(localize_rows(order_notifications, lang), use_container_width=True, hide_index=True)
