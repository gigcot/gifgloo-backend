import os
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request

from asset.application.ports.inbound.delete import DeleteAssetCommand
from asset.application.ports.inbound.get_asset_list import GetAssetListCommand
from asset.application.services.delete_asset_service import DeleteAssetService
from asset.application.services.get_asset_list_service import GetAssetListlService
from config.asset import get_asset_list_service, get_delete_asset_service
from shared.asset_category import AssetCategory

router = APIRouter(prefix="/assets", tags=["assets"])

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
def get_asset_list(
    request: Request,
    category: Optional[AssetCategory] = None,
    service: GetAssetListlService = Depends(get_asset_list_service),
):
    user_id = _get_user_id(request)
    result = service.execute(GetAssetListCommand(user_id=user_id, category=category))
    return {
        "assets": [
            {
                "asset_id": a.asset_id,
                "asset_type": a.asset_type.value,
                "category": a.category.value,
                "url": a.url,
            }
            for a in result.assets
        ]
    }


@router.delete("/{asset_id}")
def delete_asset(
    asset_id: str,
    request: Request,
    service: DeleteAssetService = Depends(get_delete_asset_service),
):
    user_id = _get_user_id(request)
    service.execute(DeleteAssetCommand(user_id, asset_id))
