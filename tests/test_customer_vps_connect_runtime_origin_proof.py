import pytest

from backend.trading.execution.broker_state import (
    BrokerState,
)


def make_state(runtime_environment):
    return BrokerState(
        account_fingerprint="Broker:123",
        equity=1000.0,
        open_position_count=0,
        pending_order_count=0,
        symbol="XAUUSD",
        bid=2500.0,
        ask=2500.2,
        spread_points=20.0,
        runtime_environment=runtime_environment,
    )


def test_local_origin_is_valid():
    assert (
        make_state("local").runtime_environment
        == "local"
    )


def test_metaquotes_vps_origin_is_valid():
    assert (
        make_state("metaquotes_vps").runtime_environment
        == "metaquotes_vps"
    )


def test_missing_origin_is_unknown():
    assert (
        make_state(None).runtime_environment
        is None
    )


def test_unknown_origin_fails_closed():
    with pytest.raises(
        ValueError,
        match="runtime_environment",
    ):
        make_state("unknown")
