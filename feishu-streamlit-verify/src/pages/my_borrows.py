from __future__ import annotations

from datetime import date
import streamlit as st


def render_my_borrows(
    user: dict,
    materials: list[dict],
    my_orders: list[dict],
    borrow_service,
    audit_service,
    focus_order_id: int | None = None,
) -> None:
    st.subheader("我的借用")
    if focus_order_id is not None:
        matched = [o for o in my_orders if int(o["id"]) == int(focus_order_id)]
        if matched:
            st.info(f"已定位到借用单 #{focus_order_id}")
            st.dataframe(matched, use_container_width=True, hide_index=True)
        else:
            st.warning(f"未找到借用单 #{focus_order_id}（可能不属于当前用户或已删除）")

    with st.expander("发起借用", expanded=True):
        material_options = {f"{m['code']} - {m['name']} (可借 {m['available_qty']})": m["id"] for m in materials if m["status"] == "available"}
        if not material_options:
            st.info("当前没有可借物资")
        else:
            selected = st.selectbox("选择物资", list(material_options.keys()))
            qty = st.number_input("借用数量", min_value=1, value=1)
            due_at = st.date_input("应还日期", value=date.today())
            note = st.text_input("备注")
            if st.button("提交借用申请", type="primary"):
                order_id = borrow_service.create_borrow_order(
                    applicant_open_id=user["open_id"],
                    material_id=material_options[selected],
                    qty=int(qty),
                    due_at=str(due_at),
                    note=note,
                )
                audit_service.log(user["open_id"], "borrow_create", "borrow_order", str(order_id), None, {"note": note})
                detail = borrow_service.get_order_detail(order_id)
                if detail and detail["status"] == "pending_approval":
                    st.success("借用申请已提交，等待管理员审批")
                else:
                    st.success("借用申请已创建并生效")
                st.rerun()

    st.markdown("### 我的借用记录")
    st.dataframe(my_orders, use_container_width=True, hide_index=True)

    borrowed = [o for o in my_orders if o["status"] in {"borrowed", "partially_returned"}]
    if borrowed:
        borrowed_ids = [o["id"] for o in borrowed]
        default_idx = 0
        if focus_order_id in borrowed_ids:
            default_idx = borrowed_ids.index(focus_order_id)
        selected_id = st.selectbox("选择要归还的借用单", borrowed_ids, index=default_idx)
        selected = next((o for o in borrowed if int(o["id"]) == int(selected_id)), None)
        max_qty = int(selected.get("remaining_qty", 1)) if selected else 1
        qty = st.number_input("本次归还数量", min_value=1, max_value=max_qty, value=max_qty)
        if st.button("归还所选借用单"):
            borrow_service.return_order_partial(int(selected_id), user["open_id"], int(qty))
            audit_service.log(
                user["open_id"],
                "borrow_return",
                "borrow_order",
                str(selected_id),
                None,
                {"return_qty": int(qty)},
            )
            st.success("归还成功")
            st.rerun()
