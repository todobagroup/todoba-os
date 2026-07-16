"""
TODOBA Trade ID Generator

Generates unique organizational Trade IDs.

A Trade ID identifies one organizational trade for its
entire lifecycle.

Format:

TRD-YYYYMMDD-XXXXXX

Example:

TRD-20260712-000001
"""

from datetime import datetime
from threading import Lock


class TradeIdGenerator:
    """
    Generate unique Trade IDs.

    Thread-safe.

    Counter restarts when the UTC date changes.
    """

    def __init__(self):

        self._lock = Lock()

        self._current_date = ""

        self._counter = 0

    def next_id(self) -> str:

        with self._lock:

            today = datetime.utcnow().strftime(
                "%Y%m%d"
            )

            if today != self._current_date:

                self._current_date = today

                self._counter = 0

            self._counter += 1

            return (
                f"TRD-{today}-"
                f"{self._counter:06d}"
            )


trade_id_generator = TradeIdGenerator()