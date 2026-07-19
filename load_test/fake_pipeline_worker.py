from contextlib import asynccontextmanager
import logging
import os

from dotenv import load_dotenv

load_dotenv(".env.loadtest")

from fastapi import FastAPI, HTTPException, Request, status
import httpx

from composition.adapter.outbound.loadtest.fake_pipeline_trigger_adapter import (
    FakePipelineTriggerAdapter,
)
from composition.application.ports.outbound.aws.pipeline_trigger_port import PipelineTriggerCommand
from shared.metrics import metrics_response


internal_secret = os.environ["INTERNAL_SECRET"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    http_client = httpx.AsyncClient(timeout=30)
    pipeline = FakePipelineTriggerAdapter(http_client)
    app.state.pipeline_trigger = pipeline
    try:
        yield
    finally:
        await pipeline.aclose()
        await http_client.aclose()


app = FastAPI(lifespan=lifespan)
logging.getLogger("uvicorn.access").disabled = (
    os.getenv("LOADTEST_UVICORN_ACCESS_LOG", "false").lower() != "true"
)


def _verify(request: Request) -> None:
    if request.headers.get("X-Internal-Secret") != internal_secret:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "인증 실패")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


app.get("/metrics")(metrics_response)


@app.post("/pipelines", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline(command: PipelineTriggerCommand, request: Request) -> None:
    _verify(request)
    await request.app.state.pipeline_trigger.trigger(command)
