import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import delete, text

sys.path.append(str(Path(__file__).resolve().parents[1]))

load_dotenv(".env.loadtest")

import asset.adapter.outbound.models  # noqa: F401
import composition.adapter.outbound.persistence.models  # noqa: F401
import credit_account.adapter.outbound.models  # noqa: F401
import user.adapter.outbound.persistence.models  # noqa: F401
from asset.adapter.outbound.models import AssetModel
from composition.adapter.outbound.persistence.models import CompositionJobModel
from config.database import Base, SessionLocal, engine
from credit_account.adapter.outbound.models import CreditAccountModel, CreditTransactionModel
from user.adapter.outbound.persistence.models import UserModel


def main() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_stat_statements"))

    Base.metadata.create_all(bind=engine)

    user_prefix = os.environ["LOADTEST_USER_PREFIX"]
    user_id_pattern = f"{user_prefix}-%"

    db = SessionLocal()
    try:
        deleted_transactions = db.execute(
            delete(CreditTransactionModel).where(
                CreditTransactionModel.account_user_id.like(user_id_pattern)
            )
        ).rowcount
        deleted_assets = db.execute(
            delete(AssetModel).where(AssetModel.user_id.like(user_id_pattern))
        ).rowcount
        deleted_jobs = db.execute(
            delete(CompositionJobModel).where(CompositionJobModel.user_id.like(user_id_pattern))
        ).rowcount
        deleted_accounts = db.execute(
            delete(CreditAccountModel).where(CreditAccountModel.user_id.like(user_id_pattern))
        ).rowcount
        deleted_users = db.execute(
            delete(UserModel).where(UserModel.id.like(user_id_pattern))
        ).rowcount
        db.commit()
    finally:
        db.close()

    print(f"deleted_users={deleted_users}")
    print(f"deleted_credit_accounts={deleted_accounts}")
    print(f"deleted_credit_transactions={deleted_transactions}")
    print(f"deleted_assets={deleted_assets}")
    print(f"deleted_composition_jobs={deleted_jobs}")


if __name__ == "__main__":
    main()
