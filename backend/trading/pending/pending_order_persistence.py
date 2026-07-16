"""
TODOBA Pending Order Persistence

Persists pending orders to disk.
"""

import json
from pathlib import Path

from backend.trading.pending.pending_order_record import (
    PendingOrderRecord,
)
from backend.trading.pending.pending_order_repository import (
    PendingOrderRepository,
)
from backend.trading.pending.pending_order_status import (
    PendingOrderStatus,
)


class PendingOrderPersistence:
    """
    Persist PendingOrderRepository to JSON.
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

    def save(
        self,
        repository: PendingOrderRepository,
    ) -> None:

        if not isinstance(
            repository,
            PendingOrderRepository,
        ):
            raise TypeError(
                "save requires "
                "PendingOrderRepository."
            )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = []

        for record in repository.all():

            payload.append(
                {
                    "pending_order_id": (
                        record.pending_order_id
                    ),
                    "symbol": record.symbol,
                    "order_type": record.order_type,
                    "volume": record.volume,
                    "entry": record.entry,
                    "sl": record.sl,
                    "tp": record.tp,
                    "status": (
                        record.status.value
                    ),
                    "order": record.order,
                }
            )

        self.storage_path.write_text(
            json.dumps(
                payload,
                indent=2,
            ),
            encoding="utf-8",
        )

    def restore(
        self,
        repository: PendingOrderRepository,
    ) -> int:

        if not isinstance(
            repository,
            PendingOrderRepository,
        ):
            raise TypeError(
                "restore requires "
                "PendingOrderRepository."
            )

        if not self.storage_path.exists():
            return 0

        payload = json.loads(
            self.storage_path.read_text(
                encoding="utf-8",
            )
        )

        count = 0

        for item in payload:

            repository.save(
                PendingOrderRecord(
                    pending_order_id=item[
                        "pending_order_id"
                    ],
                    symbol=item["symbol"],
                    order_type=item[
                        "order_type"
                    ],
                    volume=item["volume"],
                    entry=item["entry"],
                    sl=item["sl"],
                    tp=item["tp"],
                    status=PendingOrderStatus(
                        item["status"]
                    ),
                    order=item["order"],
                )
            )

            count += 1

        return count