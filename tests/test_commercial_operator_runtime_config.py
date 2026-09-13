import pytest

import backend.config as config


def _set_operator_config(
    monkeypatch,
    *,
    operator_id="operator-founder",
    operator_secret="commercial-operator-secret",
):
    monkeypatch.setattr(
        config,
        "TODOBA_COMMERCIAL_OPERATOR_ID",
        operator_id,
        raising=False,
    )
    monkeypatch.setattr(
        config,
        "TODOBA_COMMERCIAL_OPERATOR_SECRET",
        operator_secret,
        raising=False,
    )


def test_commercial_operator_credentials_are_returned_from_config(
    monkeypatch,
):
    _set_operator_config(monkeypatch)

    credentials = (
        config.get_commercial_operator_credentials()
    )

    assert credentials == (
        "operator-founder",
        "commercial-operator-secret",
    )


@pytest.mark.parametrize(
    (
        "operator_id",
        "operator_secret",
        "expected_message",
    ),
    [
        (
            "",
            "commercial-operator-secret",
            "TODOBA_COMMERCIAL_OPERATOR_ID is required",
        ),
        (
            "   ",
            "commercial-operator-secret",
            "TODOBA_COMMERCIAL_OPERATOR_ID is required",
        ),
        (
            "operator-founder",
            "",
            "TODOBA_COMMERCIAL_OPERATOR_SECRET is required",
        ),
        (
            "operator-founder",
            "   ",
            "TODOBA_COMMERCIAL_OPERATOR_SECRET is required",
        ),
    ],
)
def test_commercial_operator_config_fails_closed_when_missing(
    monkeypatch,
    operator_id,
    operator_secret,
    expected_message,
):
    _set_operator_config(
        monkeypatch,
        operator_id=operator_id,
        operator_secret=operator_secret,
    )

    with pytest.raises(
        RuntimeError,
        match=expected_message,
    ):
        config.get_commercial_operator_credentials()


def test_commercial_operator_identity_is_normalized(
    monkeypatch,
):
    _set_operator_config(
        monkeypatch,
        operator_id="  operator-founder  ",
        operator_secret="commercial-operator-secret",
    )

    operator_id, operator_secret = (
        config.get_commercial_operator_credentials()
    )

    assert operator_id == "operator-founder"
    assert operator_secret == "commercial-operator-secret"


def test_commercial_operator_secret_is_not_exposed_by_validation_error(
    monkeypatch,
):
    secret = "super-sensitive-commercial-secret"

    _set_operator_config(
        monkeypatch,
        operator_id="",
        operator_secret=secret,
    )

    with pytest.raises(RuntimeError) as exc_info:
        config.get_commercial_operator_credentials()

    assert secret not in str(exc_info.value)
