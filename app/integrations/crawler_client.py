"""크롤러 전송 오류를 HTTP 계층과 독립적으로 표현한다."""


class CrawlerUnavailableError(RuntimeError):
    """수집 연결 실패 또는 정상 종료 신호 누락."""


class CrawlerRequestError(RuntimeError):
    """상류 서비스의 요청/계약 오류."""

    def __init__(self, message: str, *, status_code: int):
        super().__init__(message)
        self.status_code = status_code
