from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hashlib
import hmac as hmac_mod
import json
import logging
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from bot.feishu_client import FeishuClient
from bot.parser import parse_message, resolve_category, ParseError, ParseTimeout
from shared.config import load_config, validate_config
from shared.database import Repository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("family-expense-bot")

cfg: dict = {}
repo: Repository | None = None
feishu: FeishuClient | None = None

WEBHOOK_PATH = "/webhook"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cfg, repo, feishu
    cfg = load_config()
    warnings = validate_config(cfg)
    for w in warnings:
        logger.warning("配置告警: %s", w)

    repo = Repository(cfg["app"]["db_path"])
    repo.init_schema()
    feishu = FeishuClient(cfg)
    logger.info("Bot 启动完成，监听端口 %s", cfg["app"]["bot_port"])
    yield
    logger.info("Bot 关闭")


app = FastAPI(title="家庭记账 Bot", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get(WEBHOOK_PATH)
async def webhook_verify(request: Request):
    """Feishu URL challenge — return the challenge token as plain text."""
    query = request.query_params
    challenge = query.get("challenge")
    if challenge:
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=400, detail="Missing challenge")


@app.post(WEBHOOK_PATH)
async def webhook_event(request: Request):
    global repo, feishu
    if not repo or not feishu:
        raise HTTPException(status_code=503, detail="Service not ready")

    body = await request.body()

    timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
    nonce = request.headers.get("X-Lark-Request-Nonce", "")
    signature = request.headers.get("X-Lark-Signature", "")

    if feishu.verification_token:
        sign_str = f"{timestamp}{nonce}{feishu.verification_token}{body.decode('utf-8')}"
        computed = hashlib.sha256(sign_str.encode("utf-8")).hexdigest()
        if not hmac_mod.compare_digest(computed, signature):
            logger.warning("签名验证失败")
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    challenge = payload.get("challenge")
    if challenge:
        return PlainTextResponse(challenge)

    event = payload.get("event", {})
    event_type = payload.get("type") or event.get("type", "")

    if event_type == "im.message.receive_v1":
        return await _handle_message(event, payload.get("header", {}))

    return JSONResponse({"code": 0})


async def _handle_message(event: dict, header: dict) -> JSONResponse:
    global repo, feishu

    message_id = header.get("event_id", "")
    if not message_id:
        return JSONResponse({"code": 0})

    existing = repo.fetch_one(
        "SELECT id FROM expenses WHERE feishu_event_id = ?",
        (message_id,),
    )
    if existing:
        logger.info("重复事件 %s，跳过", message_id)
        return JSONResponse({"code": 0})

    message = event.get("message", {})
    content_str = message.get("content", "{}")
    try:
        content = json.loads(content_str)
    except json.JSONDecodeError:
        content = {}

    text = content.get("text", "").strip()
    if not text:
        return JSONResponse({"code": 0})

    sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "")

    user = repo.fetch_one(
        "SELECT id, display_name FROM users WHERE feishu_open_id = ?",
        (sender_id,),
    )
    if not user:
        user_id = repo.execute(
            "INSERT INTO users (feishu_open_id, display_name, auth_method) VALUES (?, ?, 'feishu_oauth')",
            (sender_id, f"用户{sender_id[-4:]}"),
        )
        user = {"id": user_id, "display_name": f"用户{sender_id[-4:]}"}

    user_id = user["id"]

    cat_rows = repo.fetch_all("SELECT name FROM categories")
    known_categories = {r["name"] for r in cat_rows} if cat_rows else set()

    try:
        parsed = parse_message(text, known_categories=known_categories)
    except ParseTimeout:
        return JSONResponse({"code": 0, "msg": "解析超时"})
    except ParseError as e:
        await _send_reply(message_id, str(e))
        return JSONResponse({"code": 0})

    category_id = resolve_category(repo, parsed.category, user_id)

    try:
        repo.execute(
            """INSERT INTO expenses (user_id, category_id, amount, type, note, source, feishu_event_id)
               VALUES (?, ?, ?, ?, ?, 'feishu_bot', ?)""",
            (
                user_id,
                category_id,
                parsed.amount,
                "expense",
                parsed.note or "",
                message_id,
            ),
        )
    except Exception as exc:
        logger.error("写入支出失败: %s", exc)
        await _send_reply(message_id, "记账失败，请稍后再试")
        return JSONResponse({"code": 0})

    cat_name = repo.fetch_one("SELECT name FROM categories WHERE id = ?", (category_id,))
    cat_display = cat_name["name"] if cat_name else "其他"
    reply = f"已记录：{parsed.amount:.2f} 元 | {cat_display}" + (f" | {parsed.note}" if parsed.note else "")
    await _send_reply(message_id, reply)
    return JSONResponse({"code": 0})


async def _send_reply(message_id: str, text: str) -> None:
    global feishu
    try:
        token = feishu._get_tenant_access_token()
        resp = requests.post(
            f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"content": json.dumps({"text": text})},
            timeout=8,
        )
        if not resp.ok:
            logger.warning("回复消息失败 (%s): %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("回复消息异常: %s", exc)


if __name__ == "__main__":
    import uvicorn
    _port = cfg.get("app", {}).get("bot_port", 8000) if cfg else 8000
    uvicorn.run("bot.main:app", host="0.0.0.0", port=_port, reload=True)
