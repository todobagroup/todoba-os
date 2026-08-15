"""
TODOBA Trading Control Action Tests

Proof:

Operator command
->
deterministic ControlAction
->
Remote Trading Control boundary
"""

import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.control.control_action import (
    ControlAction,
)


def test_control_action_preserves_supported_contract():
    assert tuple(
        action.value
        for action in ControlAction
    ) == (
        "CLOSE_GREEN",
        "CLOSE_RED",
        "CLOSE_BUY",
        "CLOSE_SELL",
        "CLOSE_ALL_POSITIONS",
        "CANCEL_ALL_PENDING",
        "FLATTEN_ALL",
    )


def test_control_action_rejects_unknown_action():
    with pytest.raises(
        ValueError
    ):
        ControlAction(
            "CLOSE_UNKNOWN"
        )