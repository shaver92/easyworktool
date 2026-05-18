from pydantic import BaseModel, Field


class PagedPageResult(BaseModel):
    page: int = Field(ge=1, description="1-based 页码")
    char_count: int = 0
    ok: bool = True
    error: str | None = None


class ParsePdfPagedMeta(BaseModel):
    model_ocr: str = ""
    mock: bool = False
    warnings: list[str] = Field(default_factory=list)


class ParsePdfPagedResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    pages: list[PagedPageResult]
    meta: ParsePdfPagedMeta


class ChatMessage(BaseModel):
    role: str
    content: str


class DocumentChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)


class DocumentChatResponse(BaseModel):
    reply: str
    pages_in_context: list[int] = Field(description="本次送入模型的页码（1-based）")
    context_chars: int
    note: str = ""
    router_pages: list[int] = Field(
        default_factory=list,
        description="大模型页码路由给出的相关页（进入摘录裁剪前）",
    )


class JobQueuedResponse(BaseModel):
    job_id: str
    events_url: str = Field(description="SSE 进度流路径（相对站点根）")
    status_url: str = Field(description="JSON 轮询状态路径")


class DocumentInfoResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    pages: list[PagedPageResult]
    created_at: str
