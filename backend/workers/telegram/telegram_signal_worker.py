"""
TODOBA Telegram Signal Worker

Receives normalized Telegram IncomingSignal objects
and sends them to the TODOBA Signal Gateway.
"""

from backend.trading.signal.incoming_signal import IncomingSignal
from backend.workers.worker import Worker


class TelegramSignalWorker(Worker):
    """
    Telegram transport worker.

    The worker only hands IncomingSignal objects to SignalGateway.
    It does not parse, approve, plan, or execute trades.
    """

    def __init__(self, gateway):
        if gateway is None:
            raise ValueError(
                "Signal gateway is required."
            )

        self.gateway = gateway
        self.running = False

    def start(self) -> bool:
        self.running = True
        return True

    def stop(self) -> bool:
        self.running = False
        return True

    def execute(
        self,
        task: IncomingSignal,
    ) -> bool:
        if not self.running:
            raise RuntimeError(
                "Worker is not running."
            )

        if not isinstance(task, IncomingSignal):
            raise TypeError(
                "TelegramSignalWorker requires IncomingSignal."
            )

        return self.gateway.receive(task)