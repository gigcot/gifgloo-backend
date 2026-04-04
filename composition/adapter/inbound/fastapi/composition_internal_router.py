import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from composition.application.services.pipeline_callback_service import PipelineCallbackService
from composition.domain.value_objects.composition_stage import CompositionStage
from config.composition import get_pipeline_callback_service

router = APIRouter(prefix="/internal/compositions", tags=["internal"])

INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "")


def _verify(request: Request) -> None:
    if request.headers.get("X-Internal-Secret") != INTERNAL_SECRET:
        raise HTTPException(403, "인증 실패")


class CheckpointBody(BaseModel):
    stage: str
    durations_ms: Optional[list[int]] = None
    spec: Optional[dict] = None


class CompleteBody(BaseModel):
    draft_key: str
    result_key: str


class FailBody(BaseModel):
    reason: str


@router.post("/{job_id}/checkpoint")
def checkpoint(
    job_id: str,
    body: CheckpointBody,
    request: Request,
    service: PipelineCallbackService = Depends(get_pipeline_callback_service),
):
    _verify(request)
    service.checkpoint(
        job_id=job_id,
        stage=CompositionStage(body.stage),
        durations_ms=body.durations_ms,
        spec=body.spec,
    )


@router.post("/{job_id}/complete")
def complete(
    job_id: str,
    body: CompleteBody,
    request: Request,
    service: PipelineCallbackService = Depends(get_pipeline_callback_service),
):
    _verify(request)
    service.complete(job_id=job_id, draft_key=body.draft_key, result_key=body.result_key)


@router.post("/{job_id}/fail")
def fail(
    job_id: str,
    body: FailBody,
    request: Request,
    service: PipelineCallbackService = Depends(get_pipeline_callback_service),
):
    _verify(request)
    service.fail(job_id=job_id, reason=body.reason)
