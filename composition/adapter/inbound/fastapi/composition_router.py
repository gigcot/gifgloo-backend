import os

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form

from composition.application.ports.inbound.get_composition_status import GetCompositionStatusQuery
from composition.application.ports.inbound.request_composition import RequestCompositionCommand
from composition.application.services.get_composition_status_service import GetCompositionStatusService
from composition.application.services.request_composition_service import RequestCompositionService
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
    gif_file: UploadFile = File(...),
    target_file: UploadFile = File(...),
    service: RequestCompositionService = Depends(get_request_composition_service),
):
    user_id = _get_user_id(request)
    gif_bytes = await gif_file.read()
    target_bytes = await target_file.read()

    result = await service.execute(
        RequestCompositionCommand(
            user_id=user_id,
            gif_url=gif_url,
            gif_bytes=gif_bytes,
            target_bytes=target_bytes,
        )
    )
    return {"composition_job_id": result.composition_job_id, "result_url": result.result_url}


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
        "result_asset_id": result.result_asset_id,
        "failed_reason": result.failed_reason,
    }
