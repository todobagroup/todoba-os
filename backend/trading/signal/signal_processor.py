"""
TODOBA Signal Processor

Processes incoming signals from the signal queue.
"""

from backend.trading.parser.signal_parser import parse_signal


class SignalProcessor:

    def process(self, incoming_signal):

        if incoming_signal is None:
            raise ValueError("Incoming signal is required.")

        return parse_signal(incoming_signal.message)