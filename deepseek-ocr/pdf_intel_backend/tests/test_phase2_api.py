"""Phase 2 HTTP 契约与 MOCK 分支（不调用外网）。"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_health_phase2_shape(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["phase"] == 5
    assert "ocr_live" in data and isinstance(data["ocr_live"], bool)
    assert "use_mock" in data and data["use_mock"] is True
    assert data.get("skip_qwen") is False
    assert "documents_storage" in data and len(data["documents_storage"]) > 0
    assert "jobs_storage" in data and len(data["jobs_storage"]) > 0


def test_parse_pdf_mock_branch(client: TestClient) -> None:
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    r = client.post(
        "/api/parse-pdf",
        files={"file": ("x.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["mock"] is True
    assert data["structured"] is not None
    assert "markdown" in data and len(data["markdown"]) > 0


def test_parse_pdf_rejects_non_pdf(client: TestClient) -> None:
    pdf = b"%PDF-1.4\n"
    r = client.post(
        "/api/parse-pdf",
        files={"file": ("x.txt", io.BytesIO(pdf), "application/pdf")},
    )
    assert r.status_code == 400
