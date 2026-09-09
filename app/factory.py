"""결과 저장소와 선택적 크롤러 SSE 연결의 수명을 관리한다."""

import os
from contextlib import asynccontextmanager
from app.repositories.analysis_jobs import SQLiteJobStore

from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes import router


def create_app(*, job_store=None) -> FastAPI:
    load_dotenv()
    store = job_store or SQLiteJobStore(os.getenv("AI_RESULT_DB_PATH", "data/ai-results.db"))
    experimental = os.getenv("ENABLE_EXPERIMENTAL_COLLECTION", "0") == "1"

    @asynccontextmanager
    async def lifespan(app):
        store.initialize()
        app.state.job_store = store
        app.state.allow_legacy_defaults = os.getenv("ALLOW_LEGACY_CRAWLER_DEFAULTS", "0") == "1"
        crawler = None
        if experimental:
            from app.integrations.crawler_stream import CrawlerStreamClient
            crawler = CrawlerStreamClient()
            app.state.crawler_stream = crawler
        try:
            yield
        finally:
            if crawler is not None:
                await crawler.aclose()

    application = FastAPI(
        title="Re:view AI Analysis Service",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.include_router(router)
    if experimental:
        from app.api.collection import router as collection_router
        application.include_router(collection_router)

    @application.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/docs")

    return application
