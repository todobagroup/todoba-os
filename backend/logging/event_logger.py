"""
TODOBA Production Event Logger

Console logger for production events.
"""

import json

from backend.logging.event import (
    ProductionEvent,
)


class ProductionEventLogger:
    """
    Log immutable production events.

    Current output:
        Console

    Future outputs:
        File
        Dashboard
        Cloud
        Telegram Admin
    """

    def emit(
        self,
        event: ProductionEvent,
    ) -> None:

        print()

        print("=" * 50)

        print(
            event.occurred_at.isoformat(
                timespec="seconds"
            )
        )

        print(
            f"[{event.level}] "
            f"{event.department}"
        )

        print(event.message)

        if event.context:
            print(
                json.dumps(
                    event.context,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )
            )

        print("=" * 50)