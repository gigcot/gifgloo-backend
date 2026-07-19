import json
import logging
import os

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse

from composition.application.ports.inbound.get_composition_status import GetCompositionStatusQuery
from composition.application.ports.inbound.request_composition import RequestCompositionCommand
from composition.application.services.get_composition_list_service import GetCompositionListService
from composition.application.services.get_composition_status_service import GetCompositionStatusService
from composition.application.services.request_composition_service import RequestCompositionService
from composition.domain.value_objects.composition_status import CompositionStatus
from config.composition_loadtest import (
    get_composition_list_service,
    get_composition_status_service,
    get_request_composition_service,
)
from shared.metrics import (
    SSE_ACTIVE_CONNECTIONS,
    SSE_COMPLETED_TOTAL,
    SSE_DISCONNECT_TOTAL,
    SSE_FAILED_TOTAL,
)
from shared.request_context import current_request_path

router = APIRouter(prefix="/compositions", tags=["composition"])
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY")


def _get_user_id(request: Request) -> str:
    token = request.cookies.get("user_token")
    if not token:
        raise HTTPException(401, "인증이 필요합니다")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["user_id"]
    except Exception:
        raise HTTPException(401, "유효하지 않은 토큰입니다")


@router.get("")
async def get_composition_list(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: GetCompositionListService = Depends(get_composition_list_service),
):
    user_id = _get_user_id(request)
    jobs = await service.execute(user_id, limit, offset)
    return {
        "jobs": [
            {
                "job_id": j.job_id,
                "status": j.status.value,
                "source_gif_url": j.source_gif_url,
                "target_url": j.target_url,
                "result_url": j.result_url,
                "created_at": j.created_at,
            }
            for j in jobs
        ]
    }


@router.post("")
async def request_composition(
    request: Request,
    gif_url: str = Form(...),
    target_file: UploadFile = File(...),
    acknowledge_frame_reduction: bool = Form(False),
    service: RequestCompositionService = Depends(get_request_composition_service),
):
    user_id = _get_user_id(request)
    target_bytes = await target_file.read()

    result = await service.execute(
        RequestCompositionCommand(
            user_id=user_id,
            gif_url=gif_url,
            target_bytes=target_bytes,
            acknowledge_frame_reduction=acknowledge_frame_reduction,
        )
    )
    return {"composition_job_id": result.composition_job_id}


@router.get("/{composition_job_id}")
async def get_composition_status(
    request: Request,
    composition_job_id: str,
    service: GetCompositionStatusService = Depends(get_composition_status_service),
):
    user_id = _get_user_id(request)
    result = await service.execute(
        GetCompositionStatusQuery(
            composition_job_id=composition_job_id,
            user_id=user_id,
        )
    )
    return {
        "composition_job_id": result.composition_job_id,
        "status": result.status.value,
        "stage": result.stage.value if result.stage else None,
        "result_url": result.result_url,
        "result_asset_id": result.result_asset_id,
        "failed_reason": result.failed_reason,
    }


@router.get("/{composition_job_id}/status")
async def stream_composition_status(
    request: Request,
    composition_job_id: str,
    service: GetCompositionStatusService = Depends(get_composition_status_service),
):
    user_id = _get_user_id(request)

    async def event_generator():
        import asyncio
        terminal_sent = False
        request_path_token = current_request_path.set("/compositions/{composition_job_id}/status")
        SSE_ACTIVE_CONNECTIONS.inc()
        try:
            while True:
                if await request.is_disconnected():
                    if not terminal_sent:
                        SSE_DISCONNECT_TOTAL.inc()
                    break
                try:
                    result = await service.execute(
                        GetCompositionStatusQuery(
                            composition_job_id=composition_job_id,
                            user_id=user_id,
                        ),
                    )
                    yield f"data: {json.dumps({'status': result.status.value, 'stage': result.stage.value if result.stage else None, 'result_url': result.result_url, 'result_asset_id': result.result_asset_id, 'failed_reason': result.failed_reason})}\n\n"

                    if result.status == CompositionStatus.COMPLETED:
                        terminal_sent = True
                        SSE_COMPLETED_TOTAL.inc()
                        break

                    if result.status == CompositionStatus.FAILED:
                        terminal_sent = True
                        SSE_FAILED_TOTAL.inc()
                        break
                except Exception as e:
                    logger.error(f"SSE error: {e}")
                    yield f"data: {json.dumps({'error': 'internal error'})}\n\n"
                    break

                await asyncio.sleep(2)
        finally:
            SSE_ACTIVE_CONNECTIONS.dec()
            current_request_path.reset(request_path_token)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
