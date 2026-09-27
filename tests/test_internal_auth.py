"""내부 API 인증과 Data SSE 토큰의 TLS·동일 서버 전송 경계를 검증한다."""
import asyncio
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.crawler_settings import CrawlerSettings, load_crawler_settings
from app.factory import create_app
from app.integrations.crawler_client import CrawlerRequestError
from app.integrations.crawler_stream import CrawlerStreamClient
from app.repositories.analysis_jobs import SQLiteJobStore

TOKEN = "synthetic-test-token-not-a-real-credential"


@pytest.fixture
def secured(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("INTERNAL_TOKEN", TOKEN)
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "1")
    monkeypatch.setenv("ENABLE_EXPERIMENTAL_COLLECTION", "1")
    monkeypatch.setenv("DATA_SERVER_BASE_URL", "https://data.test")
    monkeypatch.delenv("DATA_INTERNAL_TOKEN", raising=False)
    store = SQLiteJobStore(str(tmp_path / "secured.db"))
    with TestClient(create_app(job_store=store)) as client:
        yield client, store


@pytest.mark.parametrize("path,method", [
    ("/api/v1/analyze", "post"), ("/api/v1/data/analyze", "post"),
    ("/experimental/analysis/collect/stream", "post"),
    ("/experimental/analysis/jobs/job", "get"),
])
@pytest.mark.parametrize("token", [None, "wrong"])
def test_protected_routes_reject_before_storage(secured, path, method, token):
    client, store = secured
    with patch.object(store, "create") as create, patch.object(store, "get") as get:
        response = client.request(method, path, headers={"X-Internal-Token": token} if token else {})
    assert response.status_code == 401
    assert TOKEN not in response.text
    create.assert_not_called()
    get.assert_not_called()


def test_correct_header_and_health(secured):
    client, store = secured
    assert client.get("/health").json() == {"status": "ok"}
    response = client.post("/api/v1/data/analyze", headers={"X-Internal-Token": TOKEN}, json={
        "platform": "m", "product_id": "p", "reviews": [{"review_id": "r", "content": "테스트"}],
    })
    assert response.status_code == 200
    assert TOKEN not in response.text
    assert TOKEN not in str(store.get(response.headers["X-Analysis-Job-ID"]))
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["APIKeyHeader"]["name"] == "X-Internal-Token"


def test_required_token_missing_fails_before_db(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "1")
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    store = SQLiteJobStore(str(tmp_path / "unused.db"))
    with patch.object(store, "initialize") as initialize:
        with pytest.raises(ValueError, match="INTERNAL_TOKEN is required"):
            with TestClient(create_app(job_store=store)):
                pass
    initialize.assert_not_called()


def test_data_settings_precedence_and_secret_repr(monkeypatch):
    monkeypatch.setenv("DATA_SERVER_BASE_URL", "https://data.test")
    monkeypatch.setenv("CRAWLER_BASE_URL", "http://legacy.test")
    monkeypatch.setenv("INTERNAL_TOKEN", "incoming-only")
    monkeypatch.setenv("DATA_INTERNAL_TOKEN", TOKEN)
    settings = load_crawler_settings()
    assert settings.base_url == "https://data.test"
    assert settings.internal_token.get_secret_value() == TOKEN
    assert TOKEN not in repr(settings) and TOKEN not in settings.model_dump_json()


@pytest.mark.parametrize("url", ["http://data.test", "https://user:pw@data.test", "https://data.test?token=x"])
def test_unsafe_token_destinations_rejected(url):
    with pytest.raises(ValidationError):
        CrawlerSettings(base_url=url, internal_token=TOKEN)


def test_base_url_override_cannot_downgrade_tls():
    with pytest.raises(ValidationError):
        CrawlerStreamClient(base_url="http://data.test", settings=CrawlerSettings(
            base_url="https://data.test", internal_token=TOKEN))


def test_sse_token_and_reconnect_header():
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                body = 'id: 9\nretry: 0\nevent: heartbeat\ndata: {}\n\n'
            else:
                body = 'event: done\ndata: {"job_id":"up","collected":0}\n\n'
            return httpx.Response(200, headers={"content-type":"text/event-stream"}, text=body)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://other.test") as http:
            crawler = CrawlerStreamClient(client=http, settings=CrawlerSettings(
                base_url="https://data.test", internal_token=TOKEN, max_retries=1))
            events = [e async for e in crawler.stream_reviews("mall", "p", limit=2)]
        assert len(events) == 2 and len(calls) == 2
        assert all(r.url.host == "data.test" and r.headers["X-Internal-Token"] == TOKEN for r in calls)
        assert "Last-Event-ID" not in calls[0].headers
        assert calls[1].headers["Last-Event-ID"] == "9"
        assert calls[0].url.path == "/mall/products/p/reviews/stream"
    asyncio.run(run())


@pytest.mark.parametrize("path", ["https://other.test/", "//other.test/", "/\\other.test/"])
def test_arbitrary_destination_never_receives_token(path):
    async def run():
        calls = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: calls.append(r))) as http:
            crawler = CrawlerStreamClient(client=http, settings=CrawlerSettings(
                base_url="https://data.test", internal_token=TOKEN))
            with pytest.raises(CrawlerRequestError):
                _ = [e async for e in crawler.subscribe(path)]
        assert calls == []
    asyncio.run(run())


@pytest.mark.parametrize("status", [302, 307, 401, 500])
def test_no_redirect_or_reflected_error_secret(status):
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(status, headers={"location":"https://other.test"}, text=TOKEN)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as http:
            crawler = CrawlerStreamClient(client=http, settings=CrawlerSettings(
                base_url="https://data.test", internal_token=TOKEN))
            with pytest.raises(CrawlerRequestError) as error:
                _ = [e async for e in crawler.stream_reviews("m", "p", limit=1)]
            assert TOKEN not in str(error.value)
        assert len(calls) == 1
    asyncio.run(run())
