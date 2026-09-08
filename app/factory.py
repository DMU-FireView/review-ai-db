"""외부 DB·큐 연결 없이 AI FastAPI 앱과 라우터를 생성한다."""

from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes import router


def create_app() -> FastAPI:
    load_dotenv()
    application = FastAPI(
        title="Re:view AI Analysis Service",
        version="1.0.0",
    )
    application.include_router(router)

    @application.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/docs")

    return application
