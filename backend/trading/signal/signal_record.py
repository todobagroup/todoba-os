"""
TODOBA Signal Record

Stores signal information and lifecycle status.
"""

from dataclasses import dataclass

from backend.trading.signal.incoming_signal import IncomingSignal
from backend.trading.signal.signal_status import SignalStatus


@dataclass
class SignalRecord:

    signal: IncomingSignal

    status: SignalStatus = SignalStatus.RECEIVED