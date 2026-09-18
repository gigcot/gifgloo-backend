import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from composition.application.services.pipeline_callback_service import PipelineCallbackService
from composition.domain.value_objects.composition_stage import CompositionStage
from config.composition import get_pipeline_callback_service

router = APIRouter(prefix="/internal/compositions", tags=["internal"])

INTERNAL_SECRET = os.environ["INTERNAL_SECRET"]


def _verify(request: Request) -> None:
    if request.headers.get("X-Internal-Secret") != INTERNAL_SECRET:
        raise HTTPException(403, "인증 실패")


class CheckpointBody(BaseModel):
    run_id: str
    stage: str
    durations_ms: Optional[list[int]] = None
    spec: Optional[dict] = None


class CompleteBody(BaseModel):
    run_id: str
    draft_key: str
    result_key: str


class FailBody(BaseModel):
    run_id: str
    reason: str


class RunBody(BaseModel):
    run_id: str


class EditStartedBody(RunBody):
    elapsed_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)


@router.post("/{job_id}/start")
async def start(
    job_id: str,
    body: RunBody,
    request: Request,
    service: PipelineCallbackService = Depends(get_pipeline_callback_service),
):
    _verify(request)
    await service.start(job_id, body.run_id)


@router.post("/{job_id}/edit-started")
async def edit_started(
    job_id: str,
    body: EditStartedBody,
    request: Request,
    service: PipelineCallbackService = Depends(get_pipeline_callback_service),
):
    _verify(request)
    await service.record_edit(job_id, body.run_id, body.elapsed_seconds)


@router.post("/{job_id}/checkpoint")
async def checkpoint(
    job_id: str,
    body: CheckpointBody,
    request: Request,
    service: PipelineCallbackService = Depends(get_pipeline_callback_service),
):
    _verify(request)
    await service.checkpoint(
        job_id=job_id,
        run_id=body.run_id,
        stage=CompositionStage(body.stage),
        durations_ms=body.durations_ms,
        spec=body.spec,
    )


@router.post("/{job_id}/complete")
async def complete(
    job_id: str,
    body: CompleteBody,
    request: Request,
    service: PipelineCallbackService = Depends(get_pipeline_callback_service),
):
    _verify(request)
    await service.complete(job_id=job_id, run_id=body.run_id, draft_key=body.draft_key, result_key=body.result_key)


@router.post("/{job_id}/fail")
async def fail(
    job_id: str,
    body: FailBody,
    request: Request,
    service: PipelineCallbackService = Depends(get_pipeline_callback_service),
):
    _verify(request)
    await service.fail(job_id=job_id, run_id=body.run_id, reason=body.reason)
