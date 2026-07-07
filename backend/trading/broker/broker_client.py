"""
TODOBA Broker Client Interface

Defines the contract for all broker clients.
"""

from abc import ABC, abstractmethod


class BrokerClient(ABC):
    """
    Base interface for broker communication.
    """

    @abstractmethod
    def connect(self):
        """Connect to broker."""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from broker."""
        pass

    @abstractmethod
    def is_connected(self):
        """Return connection status."""
        pass

    @abstractmethod
    def execute(self, request):
        """Execute trading request."""
        pass