import asyncio
import os
import unittest
from unittest.mock import AsyncMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test")

from user.adapter.outbound.persistence.models import UserModel
from user.adapter.outbound.persistence.sqlalchemy_user_repository import SqlAlchemyUserRepository
from user.adapter.outbound.persistence.sqlalchemy_async_user_repository import SqlAlchemyAsyncUserRepository
from user.domain.aggregates.user import User
from user.domain.value_objects.acquisition import Acquisition
from user.domain.value_objects.social_account import SocialAccount, SocialProvider


class AcquisitionPersistenceTest(unittest.TestCase):
    def test_roundtrip_and_existing_save_do_not_overwrite_acquisition(self):
        engine = create_engine("sqlite://")
        UserModel.__table__.create(engine)
        with Session(engine) as session:
            repo = SqlAlchemyUserRepository(session)
            user = User(SocialAccount(SocialProvider.GOOGLE, "123"), acquisition=Acquisition(campaign="exp001"))
            repo.save(user)
            self.assertEqual(repo.find_by_id(user.id).acquisition, user.acquisition)
            user.acquisition = Acquisition(campaign="other")
            repo.save(user)
            self.assertEqual(repo.find_by_id(user.id).acquisition.campaign, "exp001")
            async_session = AsyncMock()
            async_session.get.return_value = session.get(UserModel, user.id)
            restored = asyncio.run(SqlAlchemyAsyncUserRepository(async_session).find_by_id(user.id))
            self.assertEqual(restored.acquisition.campaign, "exp001")
            direct = User(SocialAccount(SocialProvider.GOOGLE, "456"))
            repo.save(direct)
            self.assertIsNone(repo.find_by_id(direct.id).acquisition)
        engine.dispose()
