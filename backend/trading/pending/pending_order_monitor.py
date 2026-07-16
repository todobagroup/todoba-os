"""
TODOBA Pending Order Monitor

Monitors organizational pending orders.

Current version only inspects MT5 pending orders.

Activation into TradeRecord will be introduced
by the next capability.
"""

from backend.trading.pending.pending_order_repository import (
    PendingOrderRepository,
)


class PendingOrderMonitor:
    """
    Monitor organizational pending orders.

    This component does not activate trades.
    """

    def __init__(
        self,
        *,
        repository: PendingOrderRepository,
        mt5_module,
    ):
        if not isinstance(
            repository,
            PendingOrderRepository,
        ):
            raise TypeError(
                "PendingOrderMonitor requires "
                "PendingOrderRepository."
            )

        self.repository = repository
        self.mt5 = mt5_module

    def inspect(self) -> dict:
        """
        Inspect all pending orders.

        Returns a lightweight runtime report.

        No lifecycle transition occurs here.
        """

        total = 0
        found = 0
        missing = 0

        for record in self.repository.all():

            total += 1

            orders = self.mt5.orders_get(
                ticket=record.order,
            )

            if orders:
                found += 1
            else:
                missing += 1

        return {
            "total": total,
            "found": found,
            "missing": missing,
        }