import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1]))

load_dotenv(".env.loadtest")

import composition.adapter.outbound.persistence.models  # noqa: F401
import credit_account.adapter.outbound.models  # noqa: F401
import user.adapter.outbound.persistence.models  # noqa: F401
from composition.adapter.outbound.persistence.models import CompositionJobModel
from composition.domain.value_objects.composition_status import CompositionStatus
from config.database import SessionLocal
from credit_account.adapter.outbound.models import CreditAccountModel, CreditTransactionModel
from credit_account.domain.value_objects.credit_policy import CreditPolicy
from credit_account.domain.value_objects.transaction_type import TransactionType
from user.adapter.outbound.persistence.models import UserModel


@dataclass
class UserCreditCheck:
    user_id: str
    balance: int
    expected_balance: int
    jobs: int
    failed_jobs: int
    deducts: int
    refunds: int

    @property
    def balance_ok(self) -> bool:
        return self.balance == self.expected_balance

    @property
    def deduct_ok(self) -> bool:
        return self.deducts == self.jobs

    @property
    def refund_ok(self) -> bool:
        return self.refunds == self.failed_jobs

    @property
    def ok(self) -> bool:
        return self.balance_ok and self.deduct_ok and self.refund_ok


def _count_jobs(jobs: list[CompositionJobModel], status: CompositionStatus | None = None) -> int:
    if status is None:
        return len(jobs)
    return sum(1 for job in jobs if job.status == status.value)


def _count_transactions(
    transactions: list[CreditTransactionModel],
    transaction_type: TransactionType,
) -> int:
    return sum(1 for tx in transactions if tx.transaction_type == transaction_type.value)


def _prometheus_output(checks: list[UserCreditCheck]) -> str:
    total_users = len(checks)
    inconsistent_users = sum(1 for check in checks if not check.ok)
    balance_mismatch_users = sum(1 for check in checks if not check.balance_ok)
    deduct_mismatch_users = sum(1 for check in checks if not check.deduct_ok)
    refund_mismatch_users = sum(1 for check in checks if not check.refund_ok)

    return "\n".join([
        "# HELP loadtest_credit_checked_users Loadtest users checked for credit consistency.",
        "# TYPE loadtest_credit_checked_users gauge",
        f"loadtest_credit_checked_users {total_users}",
        "# HELP loadtest_credit_inconsistent_users Loadtest users with any credit consistency mismatch.",
        "# TYPE loadtest_credit_inconsistent_users gauge",
        f"loadtest_credit_inconsistent_users {inconsistent_users}",
        "# HELP loadtest_credit_balance_mismatch_users Loadtest users with balance mismatches.",
        "# TYPE loadtest_credit_balance_mismatch_users gauge",
        f"loadtest_credit_balance_mismatch_users {balance_mismatch_users}",
        "# HELP loadtest_credit_deduct_mismatch_users Loadtest users with deduct transaction mismatches.",
        "# TYPE loadtest_credit_deduct_mismatch_users gauge",
        f"loadtest_credit_deduct_mismatch_users {deduct_mismatch_users}",
        "# HELP loadtest_credit_refund_mismatch_users Loadtest users with refund transaction mismatches.",
        "# TYPE loadtest_credit_refund_mismatch_users gauge",
        f"loadtest_credit_refund_mismatch_users {refund_mismatch_users}",
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prometheus-output", type=Path)
    args = parser.parse_args()

    user_prefix = os.environ["LOADTEST_USER_PREFIX"]
    initial_balance = int(os.environ["LOADTEST_CREDIT_BALANCE"])
    user_id_pattern = f"{user_prefix}-%"

    db = SessionLocal()
    try:
        users = (
            db.query(UserModel)
            .filter(UserModel.id.like(user_id_pattern))
            .order_by(UserModel.id)
            .all()
        )
        checks: list[UserCreditCheck] = []
        for user in users:
            account = db.get(CreditAccountModel, user.id)
            transactions = (
                db.query(CreditTransactionModel)
                .filter(CreditTransactionModel.account_user_id == user.id)
                .all()
            )
            jobs = (
                db.query(CompositionJobModel)
                .filter(CompositionJobModel.user_id == user.id)
                .all()
            )
            deducts = _count_transactions(transactions, TransactionType.DEDUCT)
            refunds = _count_transactions(transactions, TransactionType.REFUND)
            expected_balance = (
                initial_balance
                - deducts * CreditPolicy.COMPOSITION_COST
                + refunds * CreditPolicy.COMPOSITION_COST
            )
            checks.append(UserCreditCheck(
                user_id=user.id,
                balance=account.balance,
                expected_balance=expected_balance,
                jobs=_count_jobs(jobs),
                failed_jobs=_count_jobs(jobs, CompositionStatus.FAILED),
                deducts=deducts,
                refunds=refunds,
            ))
    finally:
        db.close()

    inconsistent = [check for check in checks if not check.ok]
    print(f"checked_users={len(checks)}")
    print(f"inconsistent_users={len(inconsistent)}")
    for check in inconsistent:
        print(
            " ".join([
                f"user_id={check.user_id}",
                f"balance={check.balance}",
                f"expected_balance={check.expected_balance}",
                f"jobs={check.jobs}",
                f"failed_jobs={check.failed_jobs}",
                f"deducts={check.deducts}",
                f"refunds={check.refunds}",
                f"balance_ok={check.balance_ok}",
                f"deduct_ok={check.deduct_ok}",
                f"refund_ok={check.refund_ok}",
            ])
        )

    if args.prometheus_output:
        args.prometheus_output.parent.mkdir(parents=True, exist_ok=True)
        args.prometheus_output.write_text(_prometheus_output(checks))
        print(f"prometheus_output={args.prometheus_output}")

    if inconsistent:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
