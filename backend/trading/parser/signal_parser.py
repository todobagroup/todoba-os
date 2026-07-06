"""
TODOBA Signal Parser

Parse human Telegram trading messages into Signal objects.
"""

import re

from backend.trading.models.signal import Signal
from backend.trading.symbol_resolver import resolve_symbol


def parse_signal(message: str) -> Signal:
    lines = [
        line.strip()
        for line in message.strip().splitlines()
        if line.strip()
    ]

    if not lines:
        raise ValueError("Empty signal message.")

    first_line = lines[0].upper().strip()

    parts = first_line.split()

    if len(parts) < 2:
        raise ValueError("Invalid signal header.")

    order_side = parts[0]
    raw_symbol = parts[1]

    if order_side not in ["BUY", "SELL"]:
        raise ValueError(f"Invalid order side: {order_side}")

    is_now = "NOW" in parts

    symbol = resolve_symbol(raw_symbol)

    entry = None
    sl = None
    tp = None

    for line in lines[1:]:
        key_value = re.split(r"[:=\s]+", line.strip(), maxsplit=1)

        if len(key_value) != 2:
            continue

        key = key_value[0].upper()
        value = float(key_value[1])

        if key == "ENTRY":
            entry = value
        elif key == "SL":
            sl = value
        elif key == "TP":
            tp = value

    if sl is None:
        raise ValueError("Missing SL.")

    if tp is None:
        raise ValueError("Missing TP.")

    if not is_now and entry is None:
        raise ValueError("Missing ENTRY for non-NOW signal.")

    order_type = f"{order_side} NOW" if is_now else order_side

    return Signal(
        order_type=order_type,
        symbol=symbol,
        entry=entry,
        sl=sl,
        tp=tp,
    )