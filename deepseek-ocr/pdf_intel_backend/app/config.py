from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# pdf_intel_backend/.env（不依赖进程 cwd，避免在项目根启动 uvicorn 时读不到）
_ENV_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _ENV_DIR / ".env"
_DEFAULT_DOC_STORAGE = _ENV_DIR / "data" / "documents"
_DEFAULT_JOBS_STORAGE = _ENV_DIR / "data" / "jobs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_bytes: int = 20 * 1024 * 1024

    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_model_ocr: str = "deepseek-ai/DeepSeek-OCR"
    # 控制台若显示为 Qwen-Max，请在 .env 覆盖 SILICONFLOW_MODEL_QWEN
    siliconflow_model_qwen: str = "Qwen/Qwen3-235B-A22B-Instruct-2507"
    # 为空时页码路由与文档对话均使用 siliconflow_model_qwen
    siliconflow_model_router: str = ""
    # DeepSeek-OCR 在硅基侧 max_seq_len 常为 8192，max_tokens 不得超过该上限
    siliconflow_ocr_max_tokens: int = Field(
        default=4096,
        ge=1,
        le=8192,
        description="OCR chat.completions 的 max_tokens，须 ≤ 模型 max_seq_len（硅基多为 8192）",
    )

    use_mock: bool = Field(default=False, description="为 True 时强制走 Phase1 mock，不调 SiliconFlow")
    skip_qwen: bool = Field(
        default=False,
        validation_alias=AliasChoices("SILICONFLOW_SKIP_QWEN", "SKIP_QWEN"),
        description="为 True 时只做 OCR，不调用 Qwen",
    )
    ocr_timeout_sec: float = 300.0
    llm_timeout_sec: float = 120.0
    max_markdown_chars_for_qwen: int = 120_000

    # 多页 OCR 落盘 + 文档对话
    documents_storage_dir: str = Field(
        default="",
        description="多页解析 Markdown 存储根目录；空则使用 pdf_intel_backend/data/documents",
    )
    max_pdf_pages_paged: int = Field(default=200, ge=1, le=2000)
    doc_chat_max_context_chars: int = Field(default=80_000, ge=4000, le=500_000)
    doc_chat_max_tokens: int = Field(default=2048, ge=256, le=8192)
    # 对话前先由大模型选相关页（摘录长度与超时）
    doc_page_router_snippet_chars: int = Field(default=320, ge=80, le=2000)
    doc_router_prefilter_pages: int = Field(default=96, ge=8, le=400)
    doc_router_catalog_max_chars: int = Field(default=90_000, ge=8000, le=400_000)
    doc_page_router_max_pick: int = Field(default=28, ge=1, le=80)
    doc_page_router_max_tokens: int = Field(default=512, ge=64, le=2048)
    doc_page_router_timeout_sec: float = Field(default=90.0)
    jobs_storage_dir: str = Field(default="", description="异步 OCR 任务状态目录；空则使用 data/jobs")

    @field_validator("siliconflow_api_key", mode="before")
    @classmethod
    def normalize_api_key(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        s = v.strip()
        if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
            s = s[1:-1].strip()
        return s

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ocr_enabled(self) -> bool:
        return bool(self.siliconflow_api_key.strip()) and not self.use_mock

    @property
    def documents_storage_path(self) -> Path:
        s = self.documents_storage_dir.strip()
        if s:
            return Path(s).expanduser().resolve()
        return _DEFAULT_DOC_STORAGE

    @property
    def jobs_storage_path(self) -> Path:
        s = self.jobs_storage_dir.strip()
        if s:
            return Path(s).expanduser().resolve()
        return _DEFAULT_JOBS_STORAGE

    @property
    def router_llm_model(self) -> str:
        r = self.siliconflow_model_router.strip()
        return r if r else self.siliconflow_model_qwen


settings = Settings()
