from pydantic import BaseModel, ConfigDict, Field


class ActionItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task: str = Field(description="待办或行动项描述")
    owner: str | None = None
    due: str | None = None


class StructuredSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)


class ParseMeta(BaseModel):
    model_ocr: str = ""
    model_llm: str | None = None
    warnings: list[str] = Field(default_factory=list)
    mock: bool = False
    truncated_chars: int | None = None


class ParsePdfResponse(BaseModel):
    markdown: str
    structured: StructuredSummary | None = None
    meta: ParseMeta


def mock_parse_response(filename: str, uploaded_bytes: int) -> ParsePdfResponse:
    return ParsePdfResponse(
        markdown=(
            f"# Mock 文档\n\n"
            f"（MOCK：未调用 SiliconFlow；上传 `{filename}`，{uploaded_bytes} bytes）\n\n"
            "## 第一节\n\n用于联调的占位 Markdown。\n"
        ),
        structured=StructuredSummary(
            title="Mock 标题",
            summary="MOCK 固定结构化占位。真实链路由 Qwen 基于 OCR Markdown 生成。",
            key_points=["要点 A", "要点 B"],
            action_items=[
                ActionItem(task="完成 Phase 2 OCR 联调", owner="开发", due=None),
            ],
        ),
        meta=ParseMeta(
            model_ocr="mock",
            model_llm="mock",
            warnings=["响应为 MOCK，未调用外部模型"],
            mock=True,
        ),
    )
