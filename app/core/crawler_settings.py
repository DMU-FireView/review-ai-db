"""실험적 크롤러 연결의 명시적 주소와 제한값을 검증한다."""
import os
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from urllib.parse import urlsplit


class CrawlerSettings(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, hide_input_in_errors=True)
    base_url: str = Field(min_length=1)
    internal_token: SecretStr | None = Field(default=None, repr=False)
    stream_timeout: float = Field(default=60, gt=0)
    max_retries: int = Field(default=0, ge=0, le=3)

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value):
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            raise ValueError("Explicit http(s) crawler URL without embedded credentials required")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_token_transport(self):
        if self.internal_token is not None:
            raw = self.internal_token.get_secret_value()
            if not raw or not raw.isascii() or any(c.isspace() or ord(c) < 32 for c in raw):
                raise ValueError("Data token must be a non-whitespace ASCII token")
            if urlsplit(self.base_url).scheme != "https":
                raise ValueError("Data token transmission requires HTTPS")
        return self


def load_crawler_settings() -> CrawlerSettings:
    # URL이 없는 상태에서 우리 API 자체를 크롤러로 호출하지 않는다.
    return CrawlerSettings(
        base_url=os.getenv("DATA_SERVER_BASE_URL") or os.environ.get("CRAWLER_BASE_URL", ""),
        internal_token=os.getenv("DATA_INTERNAL_TOKEN") or os.getenv("INTERNAL_TOKEN") or None,
        stream_timeout=os.getenv("CRAWLER_STREAM_TIMEOUT", "60"),
        max_retries=os.getenv("CRAWLER_MAX_RETRIES", "0"),
    )
