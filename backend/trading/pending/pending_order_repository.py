"""
TODOBA Pending Order Repository

In-memory repository for organizational pending orders.
"""

from backend.trading.pending.pending_order_record import (
    PendingOrderRecord,
)


class PendingOrderRepository:
    """
    Store PendingOrderRecord instances in memory.
    """

    def __init__(self):
        self._records: dict[
            str,
            PendingOrderRecord,
        ] = {}

    def save(
        self,
        record: PendingOrderRecord,
    ) -> None:

        if not isinstance(
            record,
            PendingOrderRecord,
        ):
            raise TypeError(
                "PendingOrderRepository requires "
                "PendingOrderRecord."
            )

        self._records[
            record.pending_order_id
        ] = record

    def get(
        self,
        pending_order_id: str,
    ) -> PendingOrderRecord | None:

        return self._records.get(
            pending_order_id
        )

    def all(
        self,
    ) -> tuple[
        PendingOrderRecord,
        ...
    ]:

        return tuple(
            self._records.values()
        )

    def remove(
        self,
        pending_order_id: str,
    ) -> bool:

        return (
            self._records.pop(
                pending_order_id,
                None,
            )
            is not None
        )