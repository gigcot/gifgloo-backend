import asyncio
import json
import os

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from composition.application.ports.inbound.get_composition_status import GetCompositionStatusQuery
from composition.application.ports.inbound.request_composition import RequestCompositionCommand
from composition.application.services.get_composition_status_service import GetCompositionStatusService
from composition.application.services.request_composition_service import RequestCompositionService
from composition.domain.value_objects.composition_status import CompositionStatus
from config.composition import get_request_composition_service, get_composition_status_service

router = APIRouter(prefix="/compositions", tags=["composition"])

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
def get_composition_status(
    request: Request,
    composition_job_id: str,
    service: GetCompositionStatusService = Depends(get_composition_status_service),
):
    user_id = _get_user_id(request)
    result = service.execute(
        GetCompositionStatusQuery(
            composition_job_id=composition_job_id,
            user_id=user_id,
        )
    )
    return {
        "composition_job_id": result.composition_job_id,
        "status": result.status,
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
        while True:
            if await request.is_disconnected():
                break
            try:
                result = service.execute(GetCompositionStatusQuery(
                    composition_job_id=composition_job_id,
                    user_id=user_id,
                ))
                yield f"data: {json.dumps({'status': result.status.value, 'result_url': result.result_url, 'result_asset_id': result.result_asset_id, 'failed_reason': result.failed_reason})}\n\n"

                if result.status in (CompositionStatus.COMPLETED, CompositionStatus.FAILED):
                    break
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                break

            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
