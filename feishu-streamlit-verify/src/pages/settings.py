from __future__ import annotations

import streamlit as st


def render_settings(cfg: dict) -> None:
    st.subheader("系统设置")
    st.write("应用策略")
    st.json(
        {
            "require_borrow_approval": cfg.get("app", {}).get("require_borrow_approval", False),
            "home_url": cfg.get("app", {}).get("home_url", ""),
        }
    )
    st.write("管理员白名单（配置文件）")
    st.code("\n".join(cfg.get("rbac", {}).get("admin_open_ids", [])) or "未配置")
    st.write("提醒策略")
    st.json(cfg.get("notify", {}))
    st.write("飞书 OAuth 配置")
    feishu_cfg = cfg.get("feishu", {})
    st.code(
        "\n".join(
            [
                f"app_id={feishu_cfg.get('app_id', '')}",
                f"base_url={feishu_cfg.get('base_url', '')}",
                f"redirect_uri={feishu_cfg.get('redirect_uri', '')}",
            ]
        )
    )
