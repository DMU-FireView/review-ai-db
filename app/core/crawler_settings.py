"""실험적 크롤러 연결의 명시적 주소와 제한값을 검증한다."""
import os
from pydantic import BaseModel, ConfigDict, Field, field_validator
from urllib.parse import urlsplit


class CrawlerSettings(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    base_url: str = Field(min_length=1)
    stream_timeout: float = Field(default=60, gt=0)
    max_retries: int = Field(default=0, ge=0, le=3)

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Explicit http(s) crawler URL without embedded credentials required")
        return value.rstrip("/")


def load_crawler_settings() -> CrawlerSettings:
    # URL이 없는 상태에서 우리 API 자체를 크롤러로 호출하지 않는다.
    return CrawlerSettings(
        base_url=os.environ["CRAWLER_BASE_URL"],
        stream_timeout=os.getenv("CRAWLER_STREAM_TIMEOUT", "60"),
        max_retries=os.getenv("CRAWLER_MAX_RETRIES", "0"),
    )
