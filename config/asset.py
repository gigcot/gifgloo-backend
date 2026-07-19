from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from asset.adapter.outbound.async_user_verification import AsyncUserVerificationAdapter
from asset.adapter.outbound.sql_alchemy_asset_repository import SqlAlchemyAssetRepository
from asset.adapter.outbound.sqlalchemy_async_asset_repository import SqlAlchemyAsyncAssetRepository
from asset.adapter.outbound.user_verification import UserVerificationAdapter
from asset.application.services.delete_asset_service import DeleteAssetService
from asset.application.services.get_asset_list_service import GetAssetListService
from config.database import get_async_db, get_db
from user.adapter.outbound.persistence.sqlalchemy_async_user_repository import SqlAlchemyAsyncUserRepository
from user.adapter.outbound.persistence.sqlalchemy_user_repository import SqlAlchemyUserRepository
from user.application.services.async_verify_user_service import AsyncVerifyUserService
from user.application.services.verify_user_service import VerifyUserService


def _make_user_verification(db: Session) -> UserVerificationAdapter:
    return UserVerificationAdapter(VerifyUserService(SqlAlchemyUserRepository(db)))


def get_asset_list_service(
    db: AsyncSession = Depends(get_async_db),
) -> GetAssetListService:
    return GetAssetListService(
        user_verification=AsyncUserVerificationAdapter(
            AsyncVerifyUserService(SqlAlchemyAsyncUserRepository(db))
        ),
        asset_repo=SqlAlchemyAsyncAssetRepository(db),
    )


def get_delete_asset_service(db: Session = Depends(get_db)) -> DeleteAssetService:
    return DeleteAssetService(
        user_verification=_make_user_verification(db),
        asset_repo=SqlAlchemyAssetRepository(db),
    )
