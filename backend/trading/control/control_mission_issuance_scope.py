"""
TODOBA Control Mission Issuance Scope

Owns shared production control-mission issuance scope.

Responsibilities:
- define authoritative production control symbols
- define dedicated internal commercial-control sender identity
- reuse the existing TODOBA execution magic-number authority

This module does not create, deliver, execute, or complete
control missions.
"""

from backend.trading.execution.execution_planner import (
    TODOBA_MAGIC_NUMBER,
)


PRODUCTION_CONTROL_ALLOWED_SYMBOLS = (
    "XAUUSD",
)

# Positive integer required by the current legacy ControlMission
# contract. This identifies internal TODOBA commercial control,
# not a Telegram user.
INTERNAL_COMMERCIAL_CONTROL_SENDER_ID = 900001
