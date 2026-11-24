from __future__ import annotations

import importlib
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import app.main as main_module


@pytest.fixture
def client_for(monkeypatch: pytest.MonkeyPatch) -> Iterator:
    def build(base_path: str, max_upload_mb: str = "10") -> TestClient:
        monkeypatch.setenv("BASE_PATH", base_path)
        monkeypatch.setenv("MAX_UPLOAD_MB", max_upload_mb)
        module = importlib.reload(main_module)
        return TestClient(module.app)

    yield build
    monkeypatch.delenv("BASE_PATH", raising=False)
    monkeypatch.delenv("MAX_UPLOAD_MB", raising=False)
    importlib.reload(main_module)


def test_normalize_base_path() -> None:
    assert main_module.normalize_base_path(None) == ""
    assert main_module.normalize_base_path("") == ""
    assert main_module.normalize_base_path("/") == ""
    assert main_module.normalize_base_path("themis") == "/themis"
    assert main_module.normalize_base_path("/themis/") == "/themis"


def test_root_base_path_serves_at_root(client_for) -> None:
    client = client_for("")
    for path in ["/", "/audit", "/healthz", "/static/app.js", "/api/demos"]:
        assert client.get(path).status_code == 200, path
    html = client.get("/audit").text
    assert 'href="/static/styles.css"' in html
    assert "window.THEMIS_BASE = \"\"" in html


def test_sub_path_serves_everything_under_prefix(client_for) -> None:
    client = client_for("/themis")
    for path in ["/themis", "/themis/", "/themis/audit", "/themis/healthz", "/themis/static/app.js", "/themis/api/demos"]:
        assert client.get(path).status_code == 200, path

    for html in [client.get("/themis").text, client.get("/themis/").text, client.get("/themis/audit").text]:
        assert 'window.THEMIS_BASE = "/themis"' in html
        assert 'href="/static' not in html
        assert 'src="/static' not in html
        assert 'href="/audit' not in html
        assert 'href="/"' not in html

    assert client.get("/audit").status_code == 404
    assert client.get("/api/demos").status_code == 404

    redirect = client.get("/", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "/themis/"


def test_demo_audit_and_pdf_under_sub_path(client_for) -> None:
    client = client_for("/themis")
    demo = client.post("/themis/api/demo/compas")
    assert demo.status_code == 200
    session_id = demo.json()["session_id"]
    audit = client.post(
        "/themis/api/audit",
        json={
            "session_id": session_id,
            "protected_attributes": ["race"],
            "outcome_column": "two_year_recid",
            "model_type": "logistic_regression",
        },
    )
    assert audit.status_code == 200, audit.text
    pdf = client.get(f"/themis/api/report/{audit.json()['report_id']}/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_upload_size_limit(client_for) -> None:
    client = client_for("", max_upload_mb="1")
    small = b"a,b\n1,0\n2,1\n"
    assert client.post("/api/upload", files={"file": ("ok.csv", small, "text/csv")}).status_code == 200

    big = b"a,b\n" + b"1,0\n" * (2 * 1024 * 1024 // 4)
    response = client.post("/api/upload", files={"file": ("big.csv", big, "text/csv")})
    assert response.status_code == 413
    assert "too large" in response.json()["detail"]
