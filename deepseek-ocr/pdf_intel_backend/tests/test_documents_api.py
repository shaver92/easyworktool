"""多页解析与文档对话 API（MOCK，不调用外网）。"""

from __future__ import annotations

import io
import time

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter


def _one_page_pdf_bytes() -> bytes:
    buf = io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    w.write(buf)
    return buf.getvalue()


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_parse_paged_mock_creates_document(client: TestClient) -> None:
    pdf = _one_page_pdf_bytes()
    r = client.post(
        "/api/documents/parse-paged",
        files={"file": ("one.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["meta"]["mock"] is True
    assert data["page_count"] == 1
    assert len(data["pages"]) == 1
    assert data["pages"][0]["ok"] is True
    doc_id = data["document_id"]
    assert len(doc_id) == 36

    info = client.get(f"/api/documents/{doc_id}")
    assert info.status_code == 200
    assert info.json()["page_count"] == 1

    md = client.get(f"/api/documents/{doc_id}/pages/1/markdown")
    assert md.status_code == 200
    assert "Mock 第 1 页" in md.json()["markdown"]


def test_parse_paged_async_job_mock(client: TestClient) -> None:
    pdf = _one_page_pdf_bytes()
    r = client.post(
        "/api/documents/parse-paged-async",
        files={"file": ("async.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    st = client.get(f"/api/documents/jobs/{job_id}")
    assert st.status_code == 200
    # 后台任务在同进程 TestClient 中可能尚未跑完，轮询等待
    for _ in range(50):
        body = client.get(f"/api/documents/jobs/{job_id}").json()
        if body.get("status") == "completed":
            assert body.get("document_id")
            assert body.get("result", {}).get("page_count") == 1
            return
        if body.get("status") == "failed":
            pytest.fail(body.get("error"))
        time.sleep(0.05)
    pytest.fail("job did not complete in time")


def test_document_chat_mock(client: TestClient) -> None:
    pdf = _one_page_pdf_bytes()
    r = client.post(
        "/api/documents/parse-paged",
        files={"file": ("c.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    doc_id = r.json()["document_id"]
    chat = client.post(
        f"/api/documents/{doc_id}/chat",
        json={"messages": [{"role": "user", "content": "摘要里写了什么？"}]},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert "MOCK" in body["reply"]
    assert body["context_chars"] > 0
    assert "router_pages" in body
    assert isinstance(body["router_pages"], list)
