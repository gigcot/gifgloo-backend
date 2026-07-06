import os
import sys
from csv import writer
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[1]))

load_dotenv(".env.loadtest")

from config.database import Base, SessionLocal, engine
from credit_account.adapter.outbound.models import CreditAccountModel
import asset.adapter.outbound.models  # noqa: F401
import composition.adapter.outbound.persistence.models  # noqa: F401
import credit_account.adapter.outbound.models  # noqa: F401
import user.adapter.outbound.persistence.models  # noqa: F401
from user.adapter.outbound.persistence.models import UserModel
from user.domain.aggregates.user import UserRole, UserStatus
from user.domain.value_objects.social_account import SocialProvider


def main() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_stat_statements"))

    Base.metadata.create_all(bind=engine)

    user_prefix = os.environ["LOADTEST_USER_PREFIX"]
    email_domain = os.environ["LOADTEST_USER_EMAIL_DOMAIN"]
    user_count = int(os.environ["LOADTEST_USER_COUNT"])
    credit_balance = int(os.environ["LOADTEST_CREDIT_BALANCE"])
    token_output_path = Path(os.environ["LOADTEST_TOKEN_OUTPUT_PATH"])
    token_output_path.parent.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        with token_output_path.open("w", newline="") as token_file:
            csv_writer = writer(token_file, lineterminator="\n")
            csv_writer.writerow(["user_id", "user_token"])

            for idx in range(1, user_count + 1):
                user_id = f"{user_prefix}-{idx:04d}"
                email = f"{user_id}@{email_domain}"

                user = db.get(UserModel, user_id)
                if user:
                    user.provider = SocialProvider.GOOGLE.value
                    user.provider_id = user_id
                    user.email = email
                    user.role = UserRole.USER.value
                    user.status = UserStatus.ACTIVE.value
                else:
                    db.add(UserModel(
                        id=user_id,
                        provider=SocialProvider.GOOGLE.value,
                        provider_id=user_id,
                        email=email,
                        role=UserRole.USER.value,
                        status=UserStatus.ACTIVE.value,
                        created_at=datetime.now(timezone.utc),
                    ))

                account = db.get(CreditAccountModel, user_id)
                if account:
                    account.balance = credit_balance
                else:
                    db.add(CreditAccountModel(user_id=user_id, balance=credit_balance))

                token = jwt.encode({"user_id": user_id}, os.environ["JWT_SECRET_KEY"], algorithm="HS256")
                csv_writer.writerow([user_id, token])

        db.commit()
    finally:
        db.close()

    print(f"LOADTEST_USER_COUNT={user_count}")
    print(f"LOADTEST_TOKEN_OUTPUT_PATH={token_output_path}")


if __name__ == "__main__":
    main()
