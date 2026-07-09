"""
TODOBA Signal Status

Defines lifecycle states of a signal.
"""

from enum import Enum


class SignalStatus(Enum):

    RECEIVED = "received"

    PROCESSING = "processing"

    EXECUTED = "executed"

    FAILED = "failed"