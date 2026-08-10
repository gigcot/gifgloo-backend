from dataclasses import dataclass


@dataclass(frozen=True)
class GetCreditSummaryResult:
    balance_before: int
    charged: int
    refunded: int
    balance_after: int
