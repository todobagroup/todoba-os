"""
TODOBA Signal Queue

Stores incoming signals waiting for processing.
"""


class SignalQueue:

    def __init__(self):
        self._signals = []

    def push(self, signal):
        self._signals.append(signal)

    def pop(self):
        if not self._signals:
            return None

        return self._signals.pop(0)

    def size(self):
        return len(self._signals)