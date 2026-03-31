from __future__ import annotations

from datetime import date
import streamlit as st

from src.ui.i18n import localize_rows, t


def render_my_borrows(
    user: dict,
    materials: list[dict],
    my_orders: list[dict],
    borrow_service,
    audit_service,
    focus_order_id: int | None = None,
) -> None:
    lang = st.session_state.get("lang", "zh")
    st.subheader(t("my_borrows", lang))
    mode = st.radio("页面模式" if lang == "zh" else "Page Mode", [t("view_only", lang), t("operate_only", lang)], horizontal=True)
    if focus_order_id is not None:
        matched = [o for o in my_orders if int(o["id"]) == int(focus_order_id)]
        if matched:
            st.info(f"已定位到借用单 #{focus_order_id}")
            st.dataframe(localize_rows(matched, lang), use_container_width=True, hide_index=True)
        else:
            st.warning(f"未找到借用单 #{focus_order_id}（可能不属于当前用户或已删除）")
    if mode == t("view_only", lang):
        st.markdown("### " + ("我的借用记录" if lang == "zh" else "My Borrow Records"))
        st.dataframe(localize_rows(my_orders, lang), use_container_width=True, hide_index=True)
        return

    material_options = {f"{m['code']} - {m['name']} (可借 {m['available_qty']})": m["id"] for m in materials if m["status"] == "available"}
    if not material_options:
        st.info("当前没有可借物资" if lang == "zh" else "No available materials.")
    else:
        selected = st.selectbox("选择物资" if lang == "zh" else "Select Material", list(material_options.keys()))
        qty = st.number_input("借用数量" if lang == "zh" else "Borrow Qty", min_value=1, value=1)
        due_at = st.date_input("应还日期" if lang == "zh" else "Due Date", value=date.today())
        note = st.text_input("备注" if lang == "zh" else "Note")
        if st.button("提交借用申请" if lang == "zh" else "Submit Borrow", type="primary"):
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
                st.success("借用申请已提交，等待管理员审批" if lang == "zh" else "Submitted and waiting approval.")
            else:
                st.success("借用申请已创建并生效" if lang == "zh" else "Borrow created successfully.")
            st.rerun()
