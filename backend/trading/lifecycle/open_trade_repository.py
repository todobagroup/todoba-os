"""
TODOBA Open Trade Repository

Persists open trades to durable storage.

Architecture:

OpenTradeRegistry
        │
        ▼
OpenTradeRepository
        │
        ▼
open_trades.json

The Repository owns storage.

The Registry owns runtime state.
"""

import json
from dataclasses import asdict
from pathlib import Path

from backend.trading.lifecycle.open_trade_registry import (
    TrackedTrade,
)
from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)
from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)


class OpenTradeRepository:
    """
    Persist tracked trades to JSON storage.
    """

    def __init__(
        self,
        storage_path: Path,
    ):
        if not isinstance(
            storage_path,
            Path,
        ):
            raise TypeError(
                "storage_path must be Path."
            )

        self.storage_path = storage_path

    def exists(self) -> bool:
        """
        Return True if storage exists.
        """

        return self.storage_path.exists()

    def clear(self) -> None:
        """
        Remove persisted storage.
        """

        if self.storage_path.exists():
            self.storage_path.unlink()

    def save(
        self,
        trades: list[TrackedTrade],
    ) -> None:
        """
        Persist tracked trades.
        """

        payload = []

        for tracked in trades:

            payload.append(
                {
                    "trade_record": {
                        **asdict(
                            tracked.trade_record
                        ),
                        "status": tracked.trade_record.status.value,
                    },
                    "position_id": tracked.position_id,
                    "context": tracked.context,
                }
            )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.storage_path.write_text(
            json.dumps(
                payload,
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def load(
        self,
    ) -> list[TrackedTrade]:
        """
        Load tracked trades.
        """

        if not self.exists():
            return []

        payload = json.loads(
            self.storage_path.read_text(
                encoding="utf-8"
            )
        )

        trades = []

        for item in payload:

            trade = TradeRecord(
                trade_id=item["trade_record"]["trade_id"],
                symbol=item["trade_record"]["symbol"],
                action=item["trade_record"]["action"],
                volume=item["trade_record"]["volume"],
                status=TradeStatus(
                    item["trade_record"]["status"]
                ),
                order=item["trade_record"]["order"],
                deal=item["trade_record"]["deal"],
            )

            trades.append(
                TrackedTrade(
                    trade_record=trade,
                    position_id=item[
                        "position_id"
                    ],
                    context=item["context"],
                )
            )

        return trades