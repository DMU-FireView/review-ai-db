"""실제 Uvicorn TCP 서버에서 health와 분석 HTTP 요청을 검증한다."""
import json
import socket
import threading
import time
from urllib.request import Request, urlopen

import uvicorn
from app.factory import create_app


def test_live_http(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_RESULT_DB_PATH", str(tmp_path / "results.db"))
    monkeypatch.setenv("ENABLE_EXPERIMENTAL_COLLECTION", "0")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(), log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started
        base = f"http://127.0.0.1:{port}"
        with urlopen(base + "/health", timeout=5) as response:
            assert response.status == 200
            assert json.load(response) == {"status": "ok"}
        payload = {"product_id": "A001", "reviews": [{
            "review_id": "1001", "content": "배송 빠르고 제품도 좋아요",
            "user_id": "user1", "review_date": "2026-09-08", "verified_purchase": True,
        }]}
        request = Request(base + "/api/v1/analyze",
                          data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            assert response.status == 200
            assert json.load(response)["results"][0]["rti"] == 88
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        assert not thread.is_alive()
