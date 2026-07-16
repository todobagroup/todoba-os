"""
TODOBA Trading Runtime Infrastructure

Assembles every Trading capability required for production.

The Infrastructure owns construction only.

It does not execute trades.
It does not monitor trades.
It does not make trading decisions.
"""

from dataclasses import dataclass
from pathlib import Path

from backend.brain.memory import MemoryEngine

from backend.trading.lifecycle.open_trade_registry import (
    OpenTradeRegistry,
)
from backend.trading.lifecycle.open_trade_repository import (
    OpenTradeRepository,
)
from backend.trading.runtime.runtime_recovery import (
    RuntimeRecovery,
)


@dataclass(frozen=True)
class TradingRuntimeInfrastructure:
    """
    Container holding shared Trading infrastructure.

    This object owns infrastructure only.

    Business logic remains inside the individual
    Trading capabilities.
    """

    memory: MemoryEngine

    registry: OpenTradeRegistry

    repository: OpenTradeRepository

    recovery: RuntimeRecovery


def build_trading_runtime_infrastructure(
    *,
    storage_path: Path,
) -> TradingRuntimeInfrastructure:
    """
    Assemble the Trading infrastructure.

    Every caller receives the exact same object graph.
    """

    if not isinstance(
        storage_path,
        Path,
    ):
        raise TypeError(
            "storage_path must be pathlib.Path."
        )

    memory = MemoryEngine()

    registry = OpenTradeRegistry()

    repository = OpenTradeRepository(
        storage_path
    )

    recovery = RuntimeRecovery(
        repository=repository,
        registry=registry,
    )

    return TradingRuntimeInfrastructure(
        memory=memory,
        registry=registry,
        repository=repository,
        recovery=recovery,
    )