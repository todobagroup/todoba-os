"""TODOBA customer payment transfer-reference codec."""

from __future__ import annotations

import base64
import re


_PAYMENT_INTENT_PREFIX = "payment-intent-"
_PAYMENT_INTENT_SUFFIX_PATTERN = re.compile(
    r"[0-9a-f]{32}"
)

_PAYMENT_TRANSFER_REFERENCE_PREFIX = "TODOBA SOFTWARE "
_PAYMENT_TRANSFER_REFERENCE_TOKEN_PATTERN = re.compile(
    r"[A-Z2-7]{26}"
)

_PAYMENT_TRANSFER_REFERENCE_PADDING = "=" * 6


def encode_payment_transfer_reference(
    *,
    payment_intent_id: str,
) -> str:
    """Encode one canonical payment-intent identity for transfer use."""

    if not isinstance(payment_intent_id, str):
        raise TypeError(
            "payment_intent_id must be str."
        )

    if not payment_intent_id.startswith(
        _PAYMENT_INTENT_PREFIX
    ):
        raise ValueError(
            "payment_intent_id is not canonical."
        )

    suffix = payment_intent_id[
        len(_PAYMENT_INTENT_PREFIX):
    ]

    if (
        _PAYMENT_INTENT_SUFFIX_PATTERN.fullmatch(
            suffix
        )
        is None
    ):
        raise ValueError(
            "payment_intent_id is not canonical."
        )

    raw_identity = bytes.fromhex(
        suffix
    )

    token = (
        base64.b32encode(
            raw_identity
        )
        .decode("ascii")
        .rstrip("=")
    )

    if (
        _PAYMENT_TRANSFER_REFERENCE_TOKEN_PATTERN.fullmatch(
            token
        )
        is None
    ):
        raise RuntimeError(
            "Payment transfer reference encoding "
            "did not converge."
        )

    return (
        f"{_PAYMENT_TRANSFER_REFERENCE_PREFIX}"
        f"{token}"
    )


def decode_payment_transfer_reference(
    *,
    transfer_reference: str,
) -> str:
    """Decode one canonical transfer reference to its intent identity."""

    if not isinstance(transfer_reference, str):
        raise TypeError(
            "transfer_reference must be str."
        )

    if not transfer_reference.startswith(
        _PAYMENT_TRANSFER_REFERENCE_PREFIX
    ):
        raise ValueError(
            "transfer_reference is not canonical."
        )

    token = transfer_reference[
        len(_PAYMENT_TRANSFER_REFERENCE_PREFIX):
    ]

    if (
        _PAYMENT_TRANSFER_REFERENCE_TOKEN_PATTERN.fullmatch(
            token
        )
        is None
    ):
        raise ValueError(
            "transfer_reference is not canonical."
        )

    try:
        raw_identity = base64.b32decode(
            token
            + _PAYMENT_TRANSFER_REFERENCE_PADDING,
            casefold=False,
        )
    except Exception as exc:
        raise ValueError(
            "transfer_reference is not canonical."
        ) from exc

    if len(raw_identity) != 16:
        raise ValueError(
            "transfer_reference is not canonical."
        )

    canonical_token = (
        base64.b32encode(
            raw_identity
        )
        .decode("ascii")
        .rstrip("=")
    )

    if canonical_token != token:
        raise ValueError(
            "transfer_reference is not canonical."
        )

    return (
        f"{_PAYMENT_INTENT_PREFIX}"
        f"{raw_identity.hex()}"
    )
