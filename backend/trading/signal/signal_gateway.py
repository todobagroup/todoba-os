"""
TODOBA Signal Gateway

Entry point for all external signals.
"""


class SignalGateway:

    def __init__(self, queue):
        self.queue = queue

    def receive(self, signal):

        if signal is None:
            raise ValueError("Signal cannot be None.")

        self.queue.push(signal)

        return True