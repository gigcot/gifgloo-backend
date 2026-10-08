import hashlib

from sqlalchemy import text
from sqlalchemy.orm import Session

from user.application.ports.outbound.transaction import UserTransaction


class SqlAlchemyUserTransaction(UserTransaction):
    def __init__(self, session: Session):
        self._session = session

    def lock(self, key: str) -> None:
        lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
        self._session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
