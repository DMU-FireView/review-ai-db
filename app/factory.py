"""FastAPI 애플리케이션을 생성하고 라우터와 생명주기를 조립한다."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes import router
from app.core.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Re:view AI Analysis Server (Real DB & Trend Integrated)",
        version="v1.0-Production",
        lifespan=lifespan,
    )
    application.include_router(router)

    @application.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/docs")

    return application
