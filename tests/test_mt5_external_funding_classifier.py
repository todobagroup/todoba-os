"""
P9A4B ? Broker-Qualified External Funding Classification.

Trusted account-bound MT5 cashflow evidence
->
broker-qualified funding classification.

This capability does NOT:
- enforce licensed capacity
- apply grace
- decide upgrade
- own billing-cycle observation
- own payment or entitlement authority

Unknown evidence must remain UNKNOWN.
"""

from datetime import UTC
from datetime import datetime
from decimal import Decimal

from backend.trading.lifecycle.mt5_account_cashflow_history_reader import (
    MT5AccountCashflowEvidence,
)

from backend.trading.lifecycle.mt5_external_funding_classifier import (
    MT5ExternalFundingClassification,
    MT5ExternalFundingClassifier,
)


OBSERVED_AT = datetime(
    2026,
    9,
    8,
    12,
    0,
    tzinfo=UTC,
)


def evidence(
    *,
    account_fingerprint="RoboForex-Pro:68353796",
    cashflow_kind="balance",
    raw_deal_type=2,
    amount=Decimal("8000.0"),
    order_ticket=0,
    position_id=0,
    magic=0,
    volume=0.0,
    price=0.0,
    symbol="",
    comment="Deposit to 68353796",
    external_id="",
):
    return MT5AccountCashflowEvidence(
        account_fingerprint=account_fingerprint,
        deal_ticket=2254467273,
        deal_time_msc=1788882804670,
        observed_at=OBSERVED_AT,
        cashflow_kind=cashflow_kind,
        raw_deal_type=raw_deal_type,
        amount=amount,
        order_ticket=order_ticket,
        deal_entry=0,
        magic=magic,
        position_id=position_id,
        deal_reason=0,
        volume=volume,
        price=price,
        symbol=symbol,
        external_id=external_id,
        comment=comment,
    )


def classify(item):
    return MT5ExternalFundingClassifier().classify(
        evidence=item
    )


def test_robo_forex_observed_deposit_is_classified():
    result = classify(
        evidence()
    )

    assert isinstance(
        result,
        MT5ExternalFundingClassification,
    )

    assert result.kind == "external_deposit"

    assert (
        result.account_fingerprint
        == "RoboForex-Pro:68353796"
    )

    assert result.deal_ticket == 2254467273
    assert result.amount == Decimal("8000.0")


def test_same_comment_on_different_broker_is_unknown():
    result = classify(
        evidence(
            account_fingerprint=(
                "OtherBroker-Pro:68353796"
            )
        )
    )

    assert result.kind == "unknown"


def test_comment_must_match_same_account_login():
    result = classify(
        evidence(
            comment="Deposit to 99999999"
        )
    )

    assert result.kind == "unknown"


def test_generic_deposit_comment_is_not_enough():
    result = classify(
        evidence(
            comment="Deposit"
        )
    )

    assert result.kind == "unknown"


def test_balance_positive_without_broker_pattern_is_unknown():
    result = classify(
        evidence(
            comment=""
        )
    )

    assert result.kind == "unknown"


def test_negative_balance_is_not_guessed_as_withdrawal():
    result = classify(
        evidence(
            amount=Decimal("-500.0"),
            comment="Withdrawal",
        )
    )

    assert result.kind == "unknown"


def test_other_cashflow_kinds_are_not_guessed_not_external():
    for kind in (
        "credit",
        "charge",
        "correction",
        "bonus",
        "commission",
        "commission_daily",
        "commission_monthly",
        "commission_agent_daily",
        "commission_agent_monthly",
        "interest",
    ):
        result = classify(
            evidence(
                cashflow_kind=kind,
                raw_deal_type={
                    "credit": 3,
                    "charge": 4,
                    "correction": 5,
                    "bonus": 6,
                    "commission": 7,
                    "commission_daily": 8,
                    "commission_monthly": 9,
                    "commission_agent_daily": 10,
                    "commission_agent_monthly": 11,
                    "interest": 12,
                }[kind],
                comment="",
            )
        )

        assert result.kind == "unknown"


def test_deposit_requires_full_observed_attribution_shape():
    mutations = (
        {"order_ticket": 1},
        {"position_id": 1},
        {"magic": 1},
        {"volume": 1.0},
        {"price": 1.0},
        {"symbol": "EURUSD"},
        {"external_id": "provider-123"},
    )

    for mutation in mutations:
        result = classify(
            evidence(
                **mutation
            )
        )

        assert result.kind == "unknown"


def test_result_contract_reserves_future_states():
    assert {
        "external_deposit",
        "external_withdrawal",
        "not_external",
        "unknown",
    } == set(
        MT5ExternalFundingClassifier.CLASSIFICATION_KINDS
    )


def test_classifier_has_no_commercial_enforcement_authority():
    classifier = MT5ExternalFundingClassifier()

    for forbidden in (
        "licensed_account_cap_usd",
        "grace_percent",
        "grace_ceiling_usd",
        "upgrade_required",
        "customer_id",
        "cycle_id",
        "payment_intent_id",
        "settlement_id",
        "entitlement_id",
    ):
        assert not hasattr(
            classifier,
            forbidden,
        )
