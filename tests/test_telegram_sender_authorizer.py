"""
TODOBA Telegram Sender Authorizer Tests

Proof:

Telegram sender identity
->
configured technician allowlist
->
authorized trading boundary
"""

import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.integrations.telegram_sender_authorizer import (
    TelegramSenderAuthorizer,
)


def test_authorizer_accepts_configured_technician():
    authorizer = TelegramSenderAuthorizer(
        authorized_sender_ids=(
            101,
            202,
        )
    )

    assert authorizer.is_authorized(
        101
    ) is True

    assert authorizer.is_authorized(
        202
    ) is True


def test_authorizer_rejects_unknown_sender():
    authorizer = TelegramSenderAuthorizer(
        authorized_sender_ids=(
            101,
        )
    )

    assert authorizer.is_authorized(
        999
    ) is False


def test_authorizer_rejects_missing_sender():
    authorizer = TelegramSenderAuthorizer(
        authorized_sender_ids=(
            101,
        )
    )

    assert authorizer.is_authorized(
        None
    ) is False


def test_authorizer_rejects_empty_allowlist():
    with pytest.raises(
        ValueError,
        match=(
            "authorized_sender_ids "
            "cannot be empty"
        ),
    ):
        TelegramSenderAuthorizer(
            authorized_sender_ids=()
        )


@pytest.mark.parametrize(
    "invalid_sender_id",
    [
        0,
        -1,
        True,
        "101",
    ],
)
def test_authorizer_rejects_invalid_configured_sender_id(
    invalid_sender_id,
):
    with pytest.raises(
        (TypeError, ValueError)
    ):
        TelegramSenderAuthorizer(
            authorized_sender_ids=(
                invalid_sender_id,
            )
        )