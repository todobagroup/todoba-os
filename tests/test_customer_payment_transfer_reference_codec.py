import base64
import inspect
import re

import pytest

from backend.commercial.customer_payment_transfer_reference_codec import (
    decode_payment_transfer_reference,
    encode_payment_transfer_reference,
)


PREFIX = "TODOBA SOFTWARE "
CANONICAL_ID = (
    "payment-intent-"
    "00112233445566778899aabbccddeeff"
)


def _expected_token(
    payment_intent_id: str,
) -> str:
    suffix = payment_intent_id.removeprefix(
        "payment-intent-"
    )

    return (
        base64.b32encode(
            bytes.fromhex(suffix)
        )
        .decode("ascii")
        .rstrip("=")
    )


def test_encode_uses_full_reversible_128_bit_identity():
    expected_token = _expected_token(
        CANONICAL_ID
    )

    reference = (
        encode_payment_transfer_reference(
            payment_intent_id=CANONICAL_ID
        )
    )

    assert reference == (
        f"{PREFIX}{expected_token}"
    )

    token = reference[len(PREFIX):]

    assert len(token) == 26
    assert re.fullmatch(
        r"[A-Z2-7]{26}",
        token,
    )

    # Full UUID information is preserved:
    # 16 bytes -> canonical Base32 -> 26 chars.
    assert (
        base64.b32decode(
            token + ("=" * 6)
        ).hex()
        == "00112233445566778899aabbccddeeff"
    )


def test_round_trip_restores_exact_payment_intent_id():
    reference = (
        encode_payment_transfer_reference(
            payment_intent_id=CANONICAL_ID
        )
    )

    decoded = (
        decode_payment_transfer_reference(
            transfer_reference=reference
        )
    )

    assert decoded == CANONICAL_ID


def test_distinct_ids_produce_distinct_reversible_references():
    first_id = (
        "payment-intent-"
        "00000000000000000000000000000001"
    )
    second_id = (
        "payment-intent-"
        "00000000000000000000000000000002"
    )

    first = encode_payment_transfer_reference(
        payment_intent_id=first_id
    )
    second = encode_payment_transfer_reference(
        payment_intent_id=second_id
    )

    assert first != second

    assert (
        decode_payment_transfer_reference(
            transfer_reference=first
        )
        == first_id
    )

    assert (
        decode_payment_transfer_reference(
            transfer_reference=second
        )
        == second_id
    )


@pytest.mark.parametrize(
    "payment_intent_id",
    [
        "",
        " ",
        "payment-intent-",
        "payment-intent-1234",
        (
            "payment-intent-"
            "00112233445566778899AABBCCDDEEFF"
        ),
        (
            "payment-intent-"
            "gg112233445566778899aabbccddeeff"
        ),
        (
            "other-intent-"
            "00112233445566778899aabbccddeeff"
        ),
    ],
)
def test_encode_fails_closed_for_noncanonical_intent_ids(
    payment_intent_id,
):
    with pytest.raises(
        (TypeError, ValueError),
    ):
        encode_payment_transfer_reference(
            payment_intent_id=payment_intent_id
        )


@pytest.mark.parametrize(
    "transfer_reference",
    [
        "",
        " ",
        "TODOBA SOFTWARE",
        "TODOBA SOFTWARE ",
        "TODOBA  SOFTWARE ABC",
        "todobA software ABC",
        (
            "TODOBA SOFTWARE "
            "AAAAAAAAAAAAAAAAAAAAAAAAA"
        ),
        (
            "TODOBA SOFTWARE "
            "AAAAAAAAAAAAAAAAAAAAAAAAAAA"
        ),
        (
            "TODOBA SOFTWARE "
            "aaaaaaaaaaaaaaaaaaaaaaaaaa"
        ),
        (
            "TODOBA SOFTWARE "
            "AAAAAAAAAAAAAAAAAAAAAAAAA0"
        ),
        (
            "OTHER SOFTWARE "
            "AAAAAAAAAAAAAAAAAAAAAAAAAA"
        ),
    ],
)
def test_decode_fails_closed_for_malformed_reference(
    transfer_reference,
):
    with pytest.raises(
        (TypeError, ValueError),
    ):
        decode_payment_transfer_reference(
            transfer_reference=transfer_reference
        )


def test_codec_rejects_non_string_inputs():
    with pytest.raises(TypeError):
        encode_payment_transfer_reference(
            payment_intent_id=None
        )

    with pytest.raises(TypeError):
        decode_payment_transfer_reference(
            transfer_reference=None
        )


def test_codec_public_signatures_do_not_accept_authority_context():
    encode_signature = inspect.signature(
        encode_payment_transfer_reference
    )

    decode_signature = inspect.signature(
        decode_payment_transfer_reference
    )

    assert list(
        encode_signature.parameters
    ) == ["payment_intent_id"]

    assert list(
        decode_signature.parameters
    ) == ["transfer_reference"]

    forbidden = {
        "customer_id",
        "order_id",
        "amount_minor",
        "operator_id",
        "bank_reference",
        "bank_code",
        "account_number",
        "settlement_id",
    }

    assert forbidden.isdisjoint(
        encode_signature.parameters
    )

    assert forbidden.isdisjoint(
        decode_signature.parameters
    )
