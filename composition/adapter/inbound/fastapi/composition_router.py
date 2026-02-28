from fastapi import APIRouter, Depends

from composition.application.ports.inbound.get_composition_status import GetCompositionStatusQuery
from composition.application.ports.inbound.request_composition import RequestCompositionCommand
from composition.application.services.get_composition_status_service import GetCompositionStatusService
from composition.application.services.request_composition_service import RequestCompositionService
from pydantic import BaseModel

router = APIRouter(prefix="/compositions", tags=["composition"])


class RequestCompositionBody(BaseModel):
    base_asset_id: str
    overlay_asset_id: str


@router.post("")
def request_composition(
    body: RequestCompositionBody,
    service: RequestCompositionService = Depends(),
    # TODO: 인증에서 user_id 추출 (JWT 등)
    user_id: str = "temp_user_id",
):
    result = service.execute(
        RequestCompositionCommand(
            user_id=user_id,
            base_asset_id=body.base_asset_id,
            overlay_asset_id=body.overlay_asset_id,
        )
    )
    return {"composition_job_id": result.composition_job_id}


@router.get("/{composition_job_id}")
def get_composition_status(
    composition_job_id: str,
    service: GetCompositionStatusService = Depends(),
    user_id: str = "temp_user_id",
):
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
