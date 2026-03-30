from __future__ import annotations

import io
import csv
import streamlit as st


def render_admin_materials(user: dict, materials: list[dict], material_service, audit_service, repo) -> None:
    st.subheader("管理员 - 物资管理")
    with st.expander("新增物资", expanded=False):
        col1, col2 = st.columns(2)
        code = col1.text_input("物资编码")
        name = col2.text_input("物资名称")
        category = col1.text_input("分类", value="未分类")
        spec = col2.text_input("规格")
        location = col1.text_input("位置")
        total_qty = col2.number_input("总库存", min_value=0, value=1)
        if st.button("保存物资"):
            payload = {
                "code": code,
                "name": name,
                "category": category,
                "spec": spec,
                "location": location,
                "owner_open_id": user["open_id"],
                "total_qty": int(total_qty),
                "available_qty": int(total_qty),
                "status": "available",
            }
            material_id = material_service.add_material(payload)
            audit_service.log(user["open_id"], "material_create", "material", str(material_id), None, payload)
            st.success("新增成功")
            st.rerun()

    with st.expander("CSV 批量导入", expanded=False):
        st.caption("字段要求: code,name,category,spec,location,total_qty")
        upload = st.file_uploader("上传 CSV", type=["csv"])
        if upload and st.button("执行导入"):
            text = upload.getvalue().decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            rows = []
            for r in reader:
                rows.append(
                    (
                        r["code"],
                        r["name"],
                        r.get("category", "未分类"),
                        r.get("spec", ""),
                        r.get("location", ""),
                        int(r.get("total_qty", 0)),
                        int(r.get("total_qty", 0)),
                        "available",
                    )
                )
            if rows:
                repo.execute_many(
                    """
                    INSERT INTO materials(code, name, category, spec, location, total_qty, available_qty, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                audit_service.log(user["open_id"], "material_import", "material", "batch", None, {"count": len(rows)})
                st.success(f"导入完成，共 {len(rows)} 条")
                st.rerun()

    st.markdown("### 物资状态维护")
    st.dataframe(materials, use_container_width=True, hide_index=True)
    if materials:
        selected_id = st.selectbox("选择物资", [m["id"] for m in materials], key="admin_material_id")
        target = next((m for m in materials if m["id"] == selected_id), None)
        if target:
            status = st.selectbox("状态", ["available", "maintenance", "retired", "off_shelf"], index=0)
            delta = st.number_input("库存调整量（可负数）", value=0, step=1)
            c1, c2 = st.columns(2)
            if c1.button("更新状态"):
                before = material_service.get_material(int(selected_id))
                material_service.update_status(int(selected_id), status)
                after = material_service.get_material(int(selected_id))
                audit_service.log(user["open_id"], "material_status", "material", str(selected_id), before, after)
                st.success("状态已更新")
                st.rerun()
            if c2.button("调整库存"):
                before = material_service.get_material(int(selected_id))
                material_service.adjust_inventory(int(selected_id), int(delta))
                repo.execute(
                    """
                    INSERT INTO inventory_transactions(material_id, action, qty_delta, reason, operator_open_id)
                    VALUES (?, 'adjust', ?, '管理员调整库存', ?)
                    """,
                    (int(selected_id), int(delta), user["open_id"]),
                )
                after = material_service.get_material(int(selected_id))
                audit_service.log(user["open_id"], "material_adjust", "material", str(selected_id), before, after)
                st.success("库存已调整")
                st.rerun()
