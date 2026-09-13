"""
TODOBA Authenticated VND Bank Reconciliation Admin API

Owns the narrow privileged HTTP boundary that allows an
authenticated commercial operator to confirm one authoritative
VND bank reconciliation.

Security rules:
- operator identity comes only from the authentication dependency
- caller cannot supply operator_id, customer_id, order_id,
  currency, reconciliation_id, or status
- caller supplies only reconciliation request identity,
  payment intent identity, observed bank reference, and observed
  amount
- currency is server-owned VND
- authoritative customer/order/amount/currency binding and replay
  protection remain owned by CustomerVndBankReconciliationService
- no evidence publication, verification assertion, settlement,
  activation, provider handling, or network access occurs here
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator

from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationRecord,
    CustomerVndBankReconciliationStatus,
)


_VND_BANK_RECONCILIATION_ADMIN_PATH = (
    "/internal/commercial/vnd-bank/reconciliations"
)


class CustomerVndBankReconciliationAdminRequest(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    reconciliation_request_id: str
    payment_intent_id: str
    bank_reference: str
    amount_minor: int

    @field_validator(
        "reconciliation_request_id",
        "payment_intent_id",
        "bank_reference",
    )
    @classmethod
    def normalize_required_string(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Value is required."
            )

        return normalized

    @field_validator(
        "amount_minor"
    )
    @classmethod
    def validate_amount_minor(
        cls,
        value: int,
    ) -> int:
        if (
            isinstance(value, bool)
            or value <= 0
        ):
            raise ValueError(
                "amount_minor must be a positive integer."
            )

        return value


class CustomerVndBankReconciliationAdminResponse(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    reconciliation_request_id: str
    reconciliation_id: str
    status: CustomerVndBankReconciliationStatus


def create_customer_vnd_bank_reconciliation_admin_router(
    *,
    commercial_operator_authentication_dependency: (
        Callable[..., str]
    ),
    reconciliation_service,
) -> APIRouter:
    if not callable(
        commercial_operator_authentication_dependency
    ):
        raise TypeError(
            "commercial_operator_authentication_dependency "
            "must be callable."
        )

    _require_owner_method(
        reconciliation_service,
        owner_name="reconciliation_service",
        method_name="confirm",
    )

    router = APIRouter()

    @router.post(
        _VND_BANK_RECONCILIATION_ADMIN_PATH,
        response_model=(
            CustomerVndBankReconciliationAdminResponse
        ),
    )
    def confirm_vnd_bank_reconciliation(
        request: CustomerVndBankReconciliationAdminRequest,
        authenticated_operator_id: str = Depends(
            commercial_operator_authentication_dependency
        ),
    ) -> CustomerVndBankReconciliationAdminResponse:
        result = reconciliation_service.confirm(
            reconciliation_request_id=(
                request.reconciliation_request_id
            ),
            payment_intent_id=(
                request.payment_intent_id
            ),
            bank_reference=(
                request.bank_reference
            ),
            amount_minor=(
                request.amount_minor
            ),
            currency="VND",
            operator_id=(
                authenticated_operator_id
            ),
        )

        if not isinstance(
            result,
            CustomerVndBankReconciliationRecord,
        ):
            raise RuntimeError(
                "VND bank reconciliation service returned "
                "invalid result."
            )

        if (
            result.reconciliation_request_id
            != request.reconciliation_request_id
        ):
            raise RuntimeError(
                "VND bank reconciliation request identity "
                "did not converge."
            )

        if (
            result.operator_id
            != authenticated_operator_id
        ):
            raise RuntimeError(
                "Authenticated operator identity "
                "did not converge."
            )

        if (
            result.status
            is not CustomerVndBankReconciliationStatus.CONFIRMED
        ):
            raise RuntimeError(
                "VND bank reconciliation did not confirm."
            )

        return (
            CustomerVndBankReconciliationAdminResponse(
                reconciliation_request_id=(
                    result.reconciliation_request_id
                ),
                reconciliation_id=(
                    result.reconciliation_id
                ),
                status=(
                    result.status
                ),
            )
        )

    return router


def _require_owner_method(
    owner,
    *,
    owner_name: str,
    method_name: str,
) -> None:
    method = getattr(
        owner,
        method_name,
        None,
    )

    if not callable(
        method
    ):
        raise TypeError(
            f"{owner_name} must expose callable "
            f"{method_name}()."
        )
