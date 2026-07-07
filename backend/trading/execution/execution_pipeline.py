"""
TODOBA Execution Pipeline

Runs the full trading flow up to MT5 request creation.
Does not send order to MT5.
"""

from backend.trading.parser.signal_parser import parse_signal
from backend.trading.validation.validation_policy import validate
from backend.trading.execution.execution_planner import create_plan
from backend.trading.execution.lot_calculator import calculate
from backend.trading.broker.broker_symbol_resolver import resolve_broker_symbol
from backend.trading.execution.execution_validator import ExecutionValidator
from backend.trading.broker.mt5_order_builder import MT5OrderBuilder


def build_execution_request(
    *,
    message: str,
    profile,
    symbol_map: dict[str, str],
    current_price: float,
):
    signal = parse_signal(message)

    validation_result = validate(signal, profile)

    if not validation_result.passed:
        raise ValueError(validation_result.errors)

    plan = create_plan(signal, profile)

    lot = calculate(profile.lot_policy_name)

    broker_symbol = resolve_broker_symbol(
        plan.symbol,
        symbol_map,
    )

    order_type = plan.order_type.replace(" NOW", "")

    price = plan.entry if plan.entry is not None else current_price

    validator = ExecutionValidator()

    validator.validate(
        symbol=broker_symbol,
        volume=lot,
        order_type=order_type,
        price=price,
        sl=plan.sl,
        tp=plan.tp,
    )

    builder = MT5OrderBuilder()

    return builder.build(
        symbol=broker_symbol,
        volume=lot,
        order_type=order_type,
        price=price,
        sl=plan.sl,
        tp=plan.tp,
        comment=plan.comment,
    )