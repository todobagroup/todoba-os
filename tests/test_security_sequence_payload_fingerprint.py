import pytest

from backend.trading.execution.security_sequence_payload_fingerprint import (
    SecuritySequencePayloadFingerprint,
)


def test_fingerprint_is_deterministic():
    payload = {
        "mission_id": "mission-001",
        "symbol": "XAUUSD",
        "sequence": 168001,
    }

    first = (
        SecuritySequencePayloadFingerprint.build(
            payload
        )
    )

    second = (
        SecuritySequencePayloadFingerprint.build(
            payload
        )
    )

    assert first == second
    assert len(first) == 64

    int(
        first,
        16,
    )


def test_fingerprint_ignores_dictionary_key_order():
    first_payload = {
        "mission_id": "mission-001",
        "symbol": "XAUUSD",
        "sequence": 168001,
    }

    second_payload = {
        "sequence": 168001,
        "mission_id": "mission-001",
        "symbol": "XAUUSD",
    }

    assert (
        SecuritySequencePayloadFingerprint.build(
            first_payload
        )
        ==
        SecuritySequencePayloadFingerprint.build(
            second_payload
        )
    )


def test_fingerprint_changes_when_payload_changes():
    original = {
        "mission_id": "mission-001",
        "symbol": "XAUUSD",
        "sequence": 168001,
    }

    changed = {
        "mission_id": "mission-001",
        "symbol": "XAUUSD",
        "sequence": 168002,
    }

    assert (
        SecuritySequencePayloadFingerprint.build(
            original
        )
        !=
        SecuritySequencePayloadFingerprint.build(
            changed
        )
    )


def test_fingerprint_rejects_non_dictionary_payload():
    with pytest.raises(
        TypeError,
        match="payload must be dict",
    ):
        SecuritySequencePayloadFingerprint.build(
            "not-a-dictionary"
        )