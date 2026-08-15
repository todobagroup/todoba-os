"""
TODOBA Control Command Parser

Converts exact bilingual operator commands into
deterministic ControlAction values.

Normal trading signals are not control commands.
"""

from backend.trading.control.control_action import (
    ControlAction,
)


_COMMAND_ACTIONS = {
    "TODOBA ĐÓNG XANH": (
        ControlAction.CLOSE_GREEN
    ),
    "TODOBA CLOSE GREEN": (
        ControlAction.CLOSE_GREEN
    ),
    "TODOBA ĐÓNG ĐỎ": (
        ControlAction.CLOSE_RED
    ),
    "TODOBA CLOSE RED": (
        ControlAction.CLOSE_RED
    ),
    "TODOBA ĐÓNG BUY": (
        ControlAction.CLOSE_BUY
    ),
    "TODOBA CLOSE BUY": (
        ControlAction.CLOSE_BUY
    ),
    "TODOBA ĐÓNG SELL": (
        ControlAction.CLOSE_SELL
    ),
    "TODOBA CLOSE SELL": (
        ControlAction.CLOSE_SELL
    ),
    "TODOBA ĐÓNG TẤT CẢ VỊ THẾ": (
        ControlAction.CLOSE_ALL_POSITIONS
    ),
    "TODOBA CLOSE ALL POSITIONS": (
        ControlAction.CLOSE_ALL_POSITIONS
    ),
    "TODOBA HỦY TẤT CẢ LỆNH CHỜ": (
        ControlAction.CANCEL_ALL_PENDING
    ),
    "TODOBA CANCEL ALL PENDING": (
        ControlAction.CANCEL_ALL_PENDING
    ),
    "TODOBA ĐÓNG VÀ HỦY TẤT CẢ": (
        ControlAction.FLATTEN_ALL
    ),
    "TODOBA FLATTEN ALL": (
        ControlAction.FLATTEN_ALL
    ),
}


def parse_control_command(
    message: str,
) -> ControlAction | None:
    """
    Parse one exact TODOBA control command.

    Return None when the message is a normal
    non-control trading signal.
    """

    if not isinstance(
        message,
        str,
    ):
        raise TypeError(
            "message must be str."
        )

    normalized_message = " ".join(
        message.strip().upper().split()
    )

    if not normalized_message:
        return None

    action = _COMMAND_ACTIONS.get(
        normalized_message
    )

    if action is not None:
        return action

    if (
        normalized_message == "TODOBA"
        or normalized_message.startswith(
            "TODOBA "
        )
    ):
        raise ValueError(
            "Unsupported TODOBA control command."
        )

    return None