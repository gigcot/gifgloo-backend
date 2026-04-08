from fastapi import Depends
from sqlalchemy.orm import Session

from config.database import get_db
from user.adapter.outbound.persistence.sqlalchemy_user_repository import SqlAlchemyUserRepository
from user.application.services.verify_user_service import VerifyUserService
from asset.adapter.outbound.sql_alchemy_asset_repository import SqlAlchemyAssetRepository
from asset.adapter.outbound.user_verification import UserVerificationAdapter
from asset.application.services.get_asset_list_service import GetAssetListlService
from asset.application.services.delete_asset_service import DeleteAssetService


def _make_user_verification(db: Session) -> UserVerificationAdapter:
    return UserVerificationAdapter(VerifyUserService(SqlAlchemyUserRepository(db)))


def get_asset_list_service(db: Session = Depends(get_db)) -> GetAssetListlService:
    return GetAssetListlService(
        user_verification=_make_user_verification(db),
        asset_repo=SqlAlchemyAssetRepository(db),
    )


def get_delete_asset_service(db: Session = Depends(get_db)) -> DeleteAssetService:
    return DeleteAssetService(
        user_verification=_make_user_verification(db),
        asset_repo=SqlAlchemyAssetRepository(db),
    )
