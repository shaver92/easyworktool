from __future__ import annotations

import streamlit as st


def _join_unique(items: list[str], value: str) -> str:
    merged = [x for x in items if x]
    if value and value not in merged:
        merged.append(value)
    return ",".join(merged)


def render_settings(cfg: dict, user: dict) -> None:
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
    st.write("管理员配置引导（可复制到 .env）")
    role_cfg = cfg.get("rbac", {})
    suggested_open_ids = _join_unique(role_cfg.get("admin_open_ids", []), user.get("open_id", ""))
    suggested_emails = _join_unique(role_cfg.get("admin_emails", []), user.get("email", ""))
    st.code(
        "\n".join(
            [
                f"RBAC_ADMIN_OPEN_IDS={suggested_open_ids}",
                f"RBAC_ADMIN_EMAILS={suggested_emails}",
            ]
        )
    )
    st.caption(
        "说明：已自动把当前登录用户拼进建议值。如需多管理员，继续用英文逗号追加。"
    )
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
