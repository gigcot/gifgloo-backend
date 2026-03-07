from fastapi import APIRouter, Depends
from pydantic import BaseModel

from asset.application.ports.inbound.delete import DeleteAssetCommand
from asset.application.ports.inbound.get_asset_list import GetAssetListCommand
from asset.application.ports.inbound.get_asset_url import GetAssetUrlCommand
from asset.application.ports.inbound.save import SaveAssetCommand
from asset.application.services.delete_asset_service import DeleteAssetService
from asset.application.services.get_asset_list_service import GetAssetListlService
from asset.application.services.get_asset_url_service import GetAssetUrlService
from asset.application.services.save_asset_service import SaveAssetService


router = APIRouter(prefix="/assets", tags=["assets"])

SECRET_KEY = "TODO: config에서 주입"  # TODO: config로 분리

@router.delete("/delete/{asset_id}")
def delete_asset(
    asset_id: str,
    user_id: str = "",  # TODO: JWT에서 추출,
    service: DeleteAssetService = Depends(),
):
    service.execute(DeleteAssetCommand(user_id, asset_id))

@router.get("/get_asset_list")
def get_asset_list(
    service: GetAssetListlService = Depends(),
    user_id: str = "",  # TODO: JWT에서 추출,
):  
    return service.execute(GetAssetListCommand(user_id))

@router.get("/get_asset_url")
def get_asset_url(
    asset_id: str,
    user_id: str = "",  # TODO: JWT에서 추출,
    service: GetAssetUrlService = Depends()
):
    return service.execute(GetAssetUrlCommand(user_id, asset_id))

@router.post("/save")
def save_asset(
    asset_type: str,
    category: str,
    url: str,
    image_data: bytes = None, # TODO: 파일 업로드 처리
    user_id: str = "",  # TODO: JWT에서 추출,
    service: SaveAssetService = Depends(),

):
    service.execute(SaveAssetCommand(user_id, category, asset_type, url, image_data))
