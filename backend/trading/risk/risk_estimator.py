"""
TODOBA Risk Estimator

Defines the interface used by the Risk Department
to obtain broker-specific calculations.
"""

from abc import ABC
from abc import abstractmethod


class RiskEstimator(ABC):
    """
    Abstract broker calculation interface.
    """

    @abstractmethod
    def estimate_expected_loss(
        self,
        *,
        symbol: str,
        order_type: str,
        entry_price: float,
        stop_loss: float,
        volume: float,
    ) -> float:
        """
        Estimate monetary loss if stop loss is hit.
        """
        raise NotImplementedError