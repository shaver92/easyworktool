# pdf_intel_backend

FastAPI：`POST /api/parse-pdf` 完成 **PDF → DeepSeek-OCR（Markdown）→ Qwen（结构化 JSON）**；支持 **MOCK**、**仅 OCR**（`SILICONFLOW_SKIP_QWEN=true`）、**Qwen 失败降级**（仍返回 `markdown` + `warnings`）。

**一键环境与启动（Conda）**见上级文档：[pdf_ocr_pipeline_plan.md](../pdf_ocr_pipeline_plan.md) 中的「Conda 环境与启动」。

## 环境变量（摘要）

复制 [`.env.example`](.env.example) 为 `.env` 并填写 `SILICONFLOW_API_KEY`。可选：

| 变量 | 说明 |
|------|------|
| `SILICONFLOW_BASE_URL` | 默认 `https://api.siliconflow.cn/v1` |
| `SILICONFLOW_MODEL_OCR` | 默认 `deepseek-ai/DeepSeek-OCR` |
| `SILICONFLOW_MODEL_QWEN` | 默认 `Qwen/Qwen3-235B-A22B-Instruct-2507`，请与控制台 **Qwen-Max** 实际 id 对齐 |
| `USE_MOCK` | `true` 时强制 mock |
| `SILICONFLOW_SKIP_QWEN` | `true` 时只做 OCR，`structured` 为 `null` |
| `CORS_ORIGINS` | 默认含 `http://localhost:5173` |
| `MAX_MARKDOWN_CHARS_FOR_QWEN` | 送 Qwen 前 Markdown 最大长度（超出截断并写入 `meta`） |

## 本地运行（简要）

```bash
conda activate pdf-intel
cd deepseek-ocr/pdf_intel_backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
```

## 验证脚本（需有效 API Key）

```bash
python scripts/verify_pipeline.py
```

## 单元测试（强制 MOCK）

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```
