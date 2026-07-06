"""
TODOBA Validation Policy

Validates a trading signal against a trading profile.
"""

from backend.trading.models.signal import Signal
from backend.trading.profile.trading_profile import TradingProfile
from backend.trading.validation.validation_result import ValidationResult


def validate(
    signal: Signal,
    profile: TradingProfile,
) -> ValidationResult:

    errors = []

    # Symbol allowed

    if signal.symbol not in profile.allowed_symbols:
        errors.append("Symbol not allowed.")

    # Risk

    if profile.risk_percent <= 0:
        errors.append("Invalid risk percent.")

    # Max trades

    if profile.max_open_trades <= 0:
        errors.append("Invalid max open trades.")

    return ValidationResult(
        passed=len(errors) == 0,
        errors=errors,
    )