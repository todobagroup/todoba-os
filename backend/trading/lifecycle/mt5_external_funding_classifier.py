"""
TODOBA MT5 External Funding Classifier

Broker-qualified interpretation of trusted,
account-bound MT5 cashflow evidence.

This capability classifies evidence only.

It does not:

- observe MT5 history
- bind customer identity
- own billing-cycle observation
- enforce licensed account capacity
- apply grace
- decide upgrade or downgrade
- own payment, settlement, or entitlement authority

Evidence that is not covered by a proven broker-qualified
rule remains ``unknown``.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from backend.trading.lifecycle.mt5_account_cashflow_history_reader import (
    MT5AccountCashflowEvidence,
)


MT5ExternalFundingKind = Literal[
    "external_deposit",
    "external_withdrawal",
    "not_external",
    "unknown",
]


@dataclass(
    frozen=True
)
class MT5ExternalFundingClassification:
    """
    Immutable classification of one trusted MT5 cashflow event.
    """

    kind: MT5ExternalFundingKind
    account_fingerprint: str
    deal_ticket: int
    amount: Decimal

    def __post_init__(
        self,
    ) -> None:
        if self.kind not in (
            "external_deposit",
            "external_withdrawal",
            "not_external",
            "unknown",
        ):
            raise ValueError(
                "Unsupported external funding classification."
            )

        if (
            not isinstance(
                self.account_fingerprint,
                str,
            )
            or not self.account_fingerprint.strip()
        ):
            raise ValueError(
                "account_fingerprint is required."
            )

        if (
            isinstance(
                self.deal_ticket,
                bool,
            )
            or not isinstance(
                self.deal_ticket,
                int,
            )
            or self.deal_ticket <= 0
        ):
            raise ValueError(
                "deal_ticket must be a positive int."
            )

        if not isinstance(
            self.amount,
            Decimal,
        ):
            raise TypeError(
                "amount must be Decimal."
            )

        if not self.amount.is_finite():
            raise ValueError(
                "amount must be finite."
            )


class MT5ExternalFundingClassifier:
    """
    Broker-qualified external-funding classifier.

    Only explicitly proven broker evidence may classify
    as external customer funding.

    Unknown evidence remains unknown.
    """

    CLASSIFICATION_KINDS = (
        "external_deposit",
        "external_withdrawal",
        "not_external",
        "unknown",
    )

    _ROBOFOREX_SERVER = "RoboForex-Pro"

    def classify(
        self,
        *,
        evidence: MT5AccountCashflowEvidence,
    ) -> MT5ExternalFundingClassification:
        if not isinstance(
            evidence,
            MT5AccountCashflowEvidence,
        ):
            raise TypeError(
                "evidence must be MT5AccountCashflowEvidence."
            )

        kind: MT5ExternalFundingKind = "unknown"

        (
            server,
            login,
        ) = self._split_account_fingerprint(
            evidence.account_fingerprint
        )

        if self._is_observed_robo_forex_deposit(
            evidence=evidence,
            server=server,
            login=login,
        ):
            kind = "external_deposit"

        return MT5ExternalFundingClassification(
            kind=kind,
            account_fingerprint=(
                evidence.account_fingerprint
            ),
            deal_ticket=evidence.deal_ticket,
            amount=evidence.amount,
        )

    @classmethod
    def _is_observed_robo_forex_deposit(
        cls,
        *,
        evidence: MT5AccountCashflowEvidence,
        server: str,
        login: str | None,
    ) -> bool:
        if (
            server != cls._ROBOFOREX_SERVER
            or login is None
        ):
            return False

        expected_comment = (
            f"Deposit to {login}"
        )

        return (
            evidence.cashflow_kind == "balance"
            and evidence.raw_deal_type == 2
            and evidence.amount > Decimal("0")
            and evidence.order_ticket == 0
            and evidence.position_id == 0
            and evidence.magic == 0
            and evidence.volume == 0.0
            and evidence.price == 0.0
            and evidence.symbol == ""
            and evidence.external_id == ""
            and evidence.comment == expected_comment
        )

    @staticmethod
    def _split_account_fingerprint(
        account_fingerprint: str,
    ) -> tuple[
        str,
        str | None,
    ]:
        if not isinstance(
            account_fingerprint,
            str,
        ):
            return (
                "",
                None,
            )

        server, separator, login = (
            account_fingerprint.rpartition(
                ":"
            )
        )

        if (
            separator != ":"
            or not server
            or not login
        ):
            return (
                "",
                None,
            )

        if not login.isdecimal():
            return (
                server,
                None,
            )

        return (
            server,
            login,
        )
