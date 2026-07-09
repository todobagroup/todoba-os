"""
TODOBA Live Execution Pipeline

Executes ExecutionPlan on MT5 demo/live environment.
"""

import MetaTrader5 as mt5

from backend.trading.execution.lot_calculator import calculate
from backend.trading.broker.broker_symbol_resolver import resolve_broker_symbol
from backend.trading.execution.execution_validator import ExecutionValidator
from backend.trading.broker.mt5_order_builder import MT5OrderBuilder
from backend.trading.broker.mt5_sender import MT5Sender


class LiveExecutionPipeline:

    def __init__(self, profile, symbol_map):
        self.profile = profile
        self.symbol_map = symbol_map

    def execute(self, plan):

        broker_symbol = resolve_broker_symbol(
            plan.symbol,
            self.symbol_map,
        )

        mt5.symbol_select(broker_symbol, True)

        symbol_info = mt5.symbol_info(broker_symbol)
        tick = mt5.symbol_info_tick(broker_symbol)

        if symbol_info is None:
            raise RuntimeError(f"Cannot read symbol info for: {broker_symbol}")

        if tick is None:
            raise RuntimeError(f"Cannot read tick for: {broker_symbol}")

        order_type = plan.order_type.replace(" NOW", "")

        if order_type == "BUY":
            price = tick.ask
        elif order_type == "SELL":
            price = tick.bid
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

        digits = symbol_info.digits
        point = symbol_info.point

        min_stop_distance = max(
            symbol_info.trade_stops_level * point,
            10 * point,
        )

        if order_type == "BUY":
            sl = min(plan.sl, price - min_stop_distance)
            tp = max(plan.tp, price + min_stop_distance)
        else:
            sl = max(plan.sl, price + min_stop_distance)
            tp = min(plan.tp, price - min_stop_distance)

        price = round(price, digits)
        sl = round(sl, digits)
        tp = round(tp, digits)

        lot = calculate(self.profile.lot_policy_name)

        ExecutionValidator().validate(
            symbol=broker_symbol,
            volume=lot,
            order_type=order_type,
            price=price,
            sl=sl,
            tp=tp,
        )

        request = MT5OrderBuilder().build(
            symbol=broker_symbol,
            volume=lot,
            order_type=order_type,
            price=price,
            sl=sl,
            tp=tp,
            comment=plan.comment,
        )

        result = MT5Sender().send(request)

        if not result.success:
            raise RuntimeError(
                f"MT5 order failed: retcode={result.retcode}, comment={result.comment}"
            )

        return result