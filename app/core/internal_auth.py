"""내부 API의 공유 토큰을 검증하며 비밀 값은 응답이나 로그에 포함하지 않는다."""
import hmac
import os

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import SecretStr

internal_header = APIKeyHeader(name="X-Internal-Token", auto_error=False,
                               description="내부 서버 간 공유 토큰")


def load_internal_token() -> SecretStr | None:
    raw = os.getenv("INTERNAL_TOKEN", "")
    if raw and (not raw.isascii() or any(c.isspace() or ord(c) < 32 for c in raw)):
        raise ValueError("INTERNAL_TOKEN must be a non-whitespace ASCII token")
    if os.getenv("REQUIRE_INTERNAL_TOKEN", "0") == "1" and not raw:
        raise ValueError("INTERNAL_TOKEN is required")
    return SecretStr(raw) if raw else None


def require_internal_token(request: Request, supplied: str | None = Security(internal_header)):
    expected = request.app.state.internal_token
    # 기존 API의 로컬 호환 모드. 운영에서는 REQUIRE_INTERNAL_TOKEN=1 필수.
    if expected is None:
        return
    if supplied is None or not hmac.compare_digest(
        supplied.encode("utf-8"), expected.get_secret_value().encode("utf-8")
    ):
        raise HTTPException(401, "Invalid or missing internal token")
