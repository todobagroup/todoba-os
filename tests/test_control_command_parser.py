"""
TODOBA Control Command Parser Tests

Proof:

Bilingual operator text
->
deterministic ControlAction
"""

import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_command_parser import (
    parse_control_command,
)


@pytest.mark.parametrize(
    (
        "message",
        "expected_action",
    ),
    [
        (
            "TODOBA ĐÓNG XANH",
            ControlAction.CLOSE_GREEN,
        ),
        (
            "TODOBA CLOSE GREEN",
            ControlAction.CLOSE_GREEN,
        ),
        (
            "TODOBA ĐÓNG ĐỎ",
            ControlAction.CLOSE_RED,
        ),
        (
            "TODOBA CLOSE RED",
            ControlAction.CLOSE_RED,
        ),
        (
            "TODOBA ĐÓNG BUY",
            ControlAction.CLOSE_BUY,
        ),
        (
            "TODOBA CLOSE BUY",
            ControlAction.CLOSE_BUY,
        ),
        (
            "TODOBA ĐÓNG SELL",
            ControlAction.CLOSE_SELL,
        ),
        (
            "TODOBA CLOSE SELL",
            ControlAction.CLOSE_SELL,
        ),
        (
            "TODOBA ĐÓNG TẤT CẢ VỊ THẾ",
            ControlAction.CLOSE_ALL_POSITIONS,
        ),
        (
            "TODOBA CLOSE ALL POSITIONS",
            ControlAction.CLOSE_ALL_POSITIONS,
        ),
        (
            "TODOBA HỦY TẤT CẢ LỆNH CHỜ",
            ControlAction.CANCEL_ALL_PENDING,
        ),
        (
            "TODOBA CANCEL ALL PENDING",
            ControlAction.CANCEL_ALL_PENDING,
        ),
        (
            "TODOBA ĐÓNG VÀ HỦY TẤT CẢ",
            ControlAction.FLATTEN_ALL,
        ),
        (
            "TODOBA FLATTEN ALL",
            ControlAction.FLATTEN_ALL,
        ),
    ],
)
def test_parse_supported_bilingual_control_command(
    message,
    expected_action,
):
    assert (
        parse_control_command(
            message
        )
        == expected_action
    )


def test_parser_normalizes_case_and_whitespace():
    assert (
        parse_control_command(
            "  todoba   close   green  "
        )
        == ControlAction.CLOSE_GREEN
    )


def test_parser_ignores_normal_trade_signal():
    assert (
        parse_control_command(
            "SELL GOLD NOW\n"
            "SL: 4400\n"
            "TP: 4370"
        )
        is None
    )


def test_parser_rejects_unknown_todoba_command():
    with pytest.raises(
        ValueError,
        match=(
            "Unsupported TODOBA "
            "control command"
        ),
    ):
        parse_control_command(
            "TODOBA CLOSE SOMETHING"
        )


def test_parser_rejects_non_string_message():
    with pytest.raises(
        TypeError,
        match="message must be str",
    ):
        parse_control_command(
            None
        )