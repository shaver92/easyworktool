from __future__ import annotations


def is_admin(user: dict, cfg: dict) -> bool:
    role_cfg = cfg.get("rbac", {})
    open_ids = set(role_cfg.get("admin_open_ids", []))
    emails = set(role_cfg.get("admin_emails", []))
    return user.get("open_id") in open_ids or (user.get("email") in emails)


def require_admin(user: dict, cfg: dict) -> bool:
    return is_admin(user, cfg)
