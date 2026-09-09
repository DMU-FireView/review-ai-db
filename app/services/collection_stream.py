"""수집 진행·분석 heartbeat를 전송하고 DB 저장 후에만 최종 결과를 만든다."""
import asyncio
import contextlib
import json
import logging
from fastapi.concurrency import run_in_threadpool
from app.contracts.stream import ReviewEvent, DoneEvent, ProgressEvent, HeartbeatEvent
from app.integrations.crawler_mapping import to_legacy_inputs, MappingNotApproved
from app.services.persisted_analysis import evaluate_and_store

LOGGER = logging.getLogger(__name__)


def sse(name: str, data: dict) -> bytes:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


async def collection_events(client, store, job_id, request, *,
                            allow_legacy_defaults=False, heartbeat_seconds=15):
    reviews = {}
    events = client.stream_reviews(request.platform, request.product_id, limit=request.limit)
    analysis_task = None
    pending = None
    terminal = False
    try:
        while True:
            pending = asyncio.create_task(anext(events))
            while not pending.done():
                ready, _ = await asyncio.wait({pending}, timeout=heartbeat_seconds)
                if not ready:
                    yield sse("heartbeat", {})
            try:
                event = pending.result()
            except StopAsyncIteration:
                raise ValueError("Crawler stream ended without done")
            pending = None
            if isinstance(event, ReviewEvent):
                if (event.platform, event.product_id) != (request.platform, request.product_id):
                    raise ValueError("Crawler returned a different product")
                key = (event.platform, event.product_id, event.review_id)
                if key in reviews and reviews[key] != event:
                    raise ValueError("Conflicting duplicate review")
                reviews[key] = event
                if len(reviews) > request.limit:
                    raise ValueError("Crawler exceeded review limit")
                # 연결 중단 시에도 이미 받은 원본을 보관한다.
                await run_in_threadpool(store.save_input, job_id, {
                    "request": request.model_dump(mode="json"),
                    "reviews": [r.model_dump(mode="json") for r in reviews.values()],
                })
                yield sse("progress", {"job_id": job_id, "collected": len(reviews),
                                       "target": request.limit})
            elif isinstance(event, ProgressEvent):
                yield sse("progress", {"job_id": job_id, "collected": len(reviews),
                                       "target": event.target})
            elif isinstance(event, HeartbeatEvent):
                yield sse("heartbeat", {})
            elif isinstance(event, DoneEvent):
                if not reviews or event.collected != len(reviews):
                    raise ValueError("Incomplete or empty collection")
                product_id = request.product_key or f"{request.platform}:{request.product_id}"
                inputs = to_legacy_inputs(list(reviews.values()), product_id,
                                          allow_legacy_defaults=allow_legacy_defaults)
                analysis_task = asyncio.create_task(run_in_threadpool(
                    evaluate_and_store, store, job_id, product_id, inputs))
                while not analysis_task.done():
                    ready, _ = await asyncio.wait({analysis_task}, timeout=heartbeat_seconds)
                    if not ready:
                        yield sse("heartbeat", {})
                result = analysis_task.result()
                terminal = True
                yield sse("result", result.model_dump(mode="json"))
                return
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        LOGGER.exception("Collection/analysis failed for %s", job_id)
        code = "MAPPING_NOT_APPROVED" if isinstance(exc, MappingNotApproved) else "COLLECTION_OR_ANALYSIS_FAILED"
        with contextlib.suppress(Exception):
            await run_in_threadpool(store.fail, job_id, code)
        terminal = True
        yield sse("error", {"job_id": job_id, "status": 503, "detail": code})
    finally:
        if pending is not None:
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await pending
        with contextlib.suppress(Exception):
            await events.aclose()
        if analysis_task is not None:
            # 이미 시작한 연산은 연결이 끊겨도 DB 저장까지 수행한다.
            # 결과는 작업 ID로 회수 가능하며 클라이언트 수신을 보장하지는 않는다.
            def consume_failure(task):
                if not task.cancelled():
                    task.exception()
            analysis_task.add_done_callback(consume_failure)
        elif not terminal:
            with contextlib.suppress(Exception):
                await run_in_threadpool(store.fail, job_id, "CLIENT_DISCONNECTED")
