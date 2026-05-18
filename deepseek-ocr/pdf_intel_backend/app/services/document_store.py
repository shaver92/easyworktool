"""多页文档：每页 Markdown 落盘 + meta.json。"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DOC_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


def is_safe_document_id(doc_id: str) -> bool:
    return bool(_DOC_ID_RE.match(doc_id.strip()))


def page_md_path(doc_dir: Path, page_one_based: int) -> Path:
    return doc_dir / f"page_{page_one_based:04d}.md"


@dataclass
class StoredDocumentMeta:
    document_id: str
    filename: str
    created_at: str
    page_count: int
    pages: list[dict[str, Any]]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "created_at": self.created_at,
            "page_count": self.page_count,
            "pages": self.pages,
        }


def create_document_dir(storage_root: Path) -> tuple[str, Path]:
    storage_root.mkdir(parents=True, exist_ok=True)
    doc_id = str(uuid.uuid4())
    d = storage_root / doc_id
    d.mkdir(parents=False, exist_ok=False)
    return doc_id, d


def write_meta(doc_dir: Path, meta: StoredDocumentMeta) -> None:
    (doc_dir / "meta.json").write_text(
        json.dumps(meta.to_json_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_meta(doc_dir: Path) -> dict[str, Any]:
    raw = (doc_dir / "meta.json").read_text(encoding="utf-8")
    return json.loads(raw)


def resolve_document_dir(storage_root: Path, doc_id: str) -> Path:
    if not is_safe_document_id(doc_id):
        raise ValueError("invalid document_id")
    d = storage_root / doc_id
    if not d.is_dir() or not (d / "meta.json").is_file():
        raise FileNotFoundError(doc_id)
    return d


def read_page_markdown(doc_dir: Path, page_one_based: int) -> str:
    p = page_md_path(doc_dir, page_one_based)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    return p.read_text(encoding="utf-8")


def iter_page_markdowns(doc_dir: Path, page_count: int) -> list[tuple[int, str]]:
    pairs: list[tuple[int, str]] = []
    for i in range(1, page_count + 1):
        p = page_md_path(doc_dir, i)
        if p.is_file():
            pairs.append((i, p.read_text(encoding="utf-8")))
    return pairs


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
