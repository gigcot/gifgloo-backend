"""Run only against the disposable local gifgloo_anonymous_verify database."""

import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

TEST_URL = os.getenv("ANONYMOUS_TEST_DATABASE_URL")
if TEST_URL:
    target = make_url(TEST_URL)
    if (
        target.get_backend_name() != "postgresql"
        or target.host != "127.0.0.1"
        or target.port != 55432
        or target.database != "gifgloo_anonymous_verify"
        or target.username != "gifgloo_verify"
    ):
        raise unittest.SkipTest("Only the explicitly named disposable local database is allowed")
    os.environ["DATABASE_URL"] = TEST_URL
    os.environ["ASYNC_DATABASE_URL"] = target.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
else:
    raise unittest.SkipTest("Set ANONYMOUS_TEST_DATABASE_URL to run PostgreSQL integration tests")

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from asset.adapter.outbound.models import AssetModel
from credit_account.adapter.outbound.models import CreditAccountModel, CreditLotModel, CreditTransactionModel
from credit_account.adapter.outbound.sql_alchemy_credit_account_repository import SqlAlchemyCreditAccountRepository
from credit_account.application.services.create_credit_account_service import CreateCreditAccountService
from shared.exceptions import AuthenticationException
from user.adapter.outbound.domain_bridges.credit_account_init_adapter import CreditAccountInitAdapter
from user.adapter.outbound.persistence.models import UserModel
from user.adapter.outbound.persistence.sqlalchemy_user_repository import SqlAlchemyUserRepository
from user.adapter.outbound.persistence.sqlalchemy_user_transaction import SqlAlchemyUserTransaction
from user.application.ports.inbound.anonymous_session import AnonymousSessionCommand
from user.application.ports.inbound.social_login import SocialLoginCommand
from user.application.ports.outbound.social_provider_port import SocialUserInfo
from user.application.services.create_anonymous_session_service import CreateAnonymousSessionService
from user.application.services.social_login_service import SocialLoginService
from user.domain.value_objects.acquisition import Acquisition
from user.domain.value_objects.signup_consent import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION, SignupConsent
from user.domain.value_objects.social_account import SocialProvider


def services(db, provider_id="postgres-provider", provider=SocialProvider.GOOGLE):
    users = SqlAlchemyUserRepository(db, commit_on_save=False)
    credit = CreditAccountInitAdapter(CreateCreditAccountService(SqlAlchemyCreditAccountRepository(db, commit_on_save=False)))
    transaction = SqlAlchemyUserTransaction(db)
    social = Mock()
    social.get_user_info.return_value = SocialUserInfo(provider, provider_id, None)
    return (
        CreateAnonymousSessionService(users, credit, transaction),
        SocialLoginService(social, users, credit, transaction),
    )


def login_command(anonymous_id=None, provider=SocialProvider.GOOGLE):
    return SocialLoginCommand(
        provider, "provider-response-stub",
        SignupConsent.record(CURRENT_TERMS_VERSION, CURRENT_PRIVACY_VERSION, True),
        anonymous_user_id=anonymous_id,
        anonymous_session_version=0 if anonymous_id else None,
    )


@unittest.skipUnless(TEST_URL, "Explicit disposable PostgreSQL URL required")
class AnonymousPostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(TEST_URL, pool_size=10)
        cls.config = Config("alembic.ini")
        # Each run requires a fresh database; never reset or truncate an existing one.
        if inspect(cls.engine).get_table_names():
            raise unittest.SkipTest("Database is not empty; use a fresh disposable container")
        command.upgrade(cls.config, "202609290001")
        with cls.engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO users (id, provider, provider_id, role, status, created_at, is_fourteen_or_older)
                VALUES ('migration-existing', 'GOOGLE', 'migration-provider', 'USER', 'ACTIVE', now(), false),
                       ('migration-duplicate', 'GOOGLE', 'migration-provider', 'USER', 'ACTIVE', now(), false)
            """))
        try:
            command.upgrade(cls.config, "head")
        except IntegrityError:
            cls.duplicate_rejected = True
        else:
            cls.duplicate_rejected = False
        cls.columns_after_failed_upgrade = {c["name"]: c for c in inspect(cls.engine).get_columns("users")}
        with cls.engine.begin() as connection:
            cls.revision_after_failed_upgrade = connection.scalar(text("SELECT version_num FROM alembic_version"))
            connection.execute(text("DELETE FROM users WHERE id = 'migration-duplicate'"))
        command.upgrade(cls.config, "head")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def test_migration_preserves_member_and_rejects_duplicate_without_partial_schema(self):
        self.assertTrue(self.duplicate_rejected)
        self.assertEqual(self.revision_after_failed_upgrade, "202609290001")
        self.assertNotIn("session_version", self.columns_after_failed_upgrade)
        self.assertFalse(self.columns_after_failed_upgrade["provider"]["nullable"])
        with Session(self.engine) as db:
            member = db.get(UserModel, "migration-existing")
            self.assertEqual((member.provider, member.provider_id, member.session_version), ("GOOGLE", "migration-provider", 0))
            self.assertEqual(db.scalar(text("SELECT version_num FROM alembic_version")), ScriptDirectory.from_config(self.config).get_current_head())

    def test_concurrent_anonymous_preparation_grants_once(self):
        user_id = str(uuid.uuid4())
        barrier = Barrier(8)

        def prepare(_):
            with Session(self.engine) as db:
                anonymous, _ = services(db)
                barrier.wait(timeout=10)
                return anonymous.execute(AnonymousSessionCommand(user_id))

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(prepare, range(8)))
        self.assertEqual(sum(r.created for r in results), 1)
        self.assertEqual({r.user_id for r in results}, {user_id})
        self.assert_initial_grant(user_id)

    def test_concurrent_new_social_signup_grants_once(self):
        provider_id = str(uuid.uuid4())
        barrier = Barrier(8)

        def login(_):
            with Session(self.engine) as db:
                _, social = services(db, provider_id)
                barrier.wait(timeout=10)
                return social.execute(login_command())

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(login, range(8)))
        self.assertEqual(sum(r.is_new_user for r in results), 1)
        self.assertEqual(len({r.user_id for r in results}), 1)
        self.assert_initial_grant(results[0].user_id)

    def test_concurrent_upgrade_preserves_identity_assets_acquisition_and_expiration(self):
        user_id, asset_id, provider_id = (str(uuid.uuid4()) for _ in range(3))
        with Session(self.engine) as db:
            anonymous, _ = services(db)
            anonymous.execute(AnonymousSessionCommand(user_id, Acquisition(campaign="exp001_run01")))
            db.add(AssetModel(id=asset_id, user_id=user_id, asset_type="GIF", category="RESULT", status="COMPLETED", storage_url="https://example.invalid/test.gif"))
            db.commit()
            original_expiration = db.scalar(select(CreditLotModel.expires_at).where(CreditLotModel.account_user_id == user_id))
        barrier = Barrier(8)

        def login(_):
            with Session(self.engine) as db:
                _, social = services(db, provider_id)
                barrier.wait(timeout=10)
                return social.execute(login_command(user_id))

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(login, range(8)))
        self.assertEqual({r.user_id for r in results}, {user_id})
        self.assertEqual(sum(r.is_new_user for r in results), 1)
        with Session(self.engine) as db:
            self.assertEqual(db.get(UserModel, user_id).session_version, 1)
            self.assertEqual(db.get(UserModel, user_id).acquisition_campaign, "exp001_run01")
            self.assertEqual(db.get(AssetModel, asset_id).user_id, user_id)
            self.assertEqual(db.scalar(select(CreditLotModel.expires_at).where(CreditLotModel.account_user_id == user_id)), original_expiration)
        self.assert_initial_grant(user_id)

    def test_existing_member_login_does_not_merge_anonymous_balance(self):
        anonymous_id, provider_id = str(uuid.uuid4()), str(uuid.uuid4())
        with Session(self.engine) as db:
            anonymous, social = services(db, provider_id)
            anonymous.execute(AnonymousSessionCommand(anonymous_id))
            member = social.execute(login_command())
            returned = social.execute(login_command(anonymous_id))
            self.assertEqual(returned.user_id, member.user_id)
            self.assertFalse(returned.is_new_user)
            self.assertIsNone(db.get(UserModel, anonymous_id).provider)
        self.assert_initial_grant(anonymous_id)
        self.assert_initial_grant(member.user_id)

    def test_credit_failure_rolls_back_all_rows(self):
        user_id = str(uuid.uuid4())
        with Session(self.engine) as db:
            users = SqlAlchemyUserRepository(db, commit_on_save=False)
            credit = CreditAccountInitAdapter(CreateCreditAccountService(SqlAlchemyCreditAccountRepository(db, commit_on_save=False)))
            original = credit.init_account

            def fail_after_flush(identity):
                original(identity)
                raise AuthenticationException("injected grant failure")

            credit.init_account = fail_after_flush
            service = CreateAnonymousSessionService(users, credit, SqlAlchemyUserTransaction(db))
            with self.assertRaises(AuthenticationException):
                service.execute(AnonymousSessionCommand(user_id))
        with Session(self.engine) as db:
            self.assertIsNone(db.get(UserModel, user_id))
            self.assertIsNone(db.get(CreditAccountModel, user_id))
            self.assertEqual(db.scalars(select(CreditLotModel).where(CreditLotModel.account_user_id == user_id)).all(), [])
            self.assertEqual(db.scalars(select(CreditTransactionModel).where(CreditTransactionModel.account_user_id == user_id)).all(), [])

    def test_social_pair_constraint_and_multiple_anonymous_users(self):
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        with Session(self.engine) as db:
            anonymous, _ = services(db)
            for user_id in ids:
                anonymous.execute(AnonymousSessionCommand(user_id))
            with self.assertRaises(IntegrityError):
                db.execute(text("UPDATE users SET provider = 'GOOGLE' WHERE id = :id"), {"id": ids[0]})
                db.commit()
            db.rollback()
            self.assertIsNone(db.get(UserModel, ids[0]).provider)

    def assert_initial_grant(self, user_id):
        with Session(self.engine) as db:
            self.assertEqual(db.get(CreditAccountModel, user_id).balance, 20)
            self.assertEqual(len(db.scalars(select(CreditLotModel).where(CreditLotModel.account_user_id == user_id)).all()), 1)
            self.assertEqual(len(db.scalars(select(CreditTransactionModel).where(CreditTransactionModel.account_user_id == user_id)).all()), 1)
