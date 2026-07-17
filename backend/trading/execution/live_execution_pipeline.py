"""
TODOBA Live Execution Pipeline

Executes an ExecutionPlan using the
TODOBA Stable Lot Policy.

Returns:
- TradeRecord for market execution;
- PendingOrderRecord for pending execution.
"""

import MetaTrader5 as mt5

from backend.trading.broker.broker_symbol_resolver import (
    resolve_broker_symbol,
)
from backend.trading.broker.mt5_order_builder import (
    MT5OrderBuilder,
)
from backend.trading.broker.mt5_sender import (
    MT5Sender,
)
from backend.trading.execution.execution_validator import (
    ExecutionValidator,
)
from backend.trading.lifecycle.trade_id_generator import (
    trade_id_generator,
)
from backend.trading.lifecycle.trade_record_builder import (
    TradeRecordBuilder,
)
from backend.trading.pending.pending_order_record_builder import (
    PendingOrderRecordBuilder,
)
from backend.trading.risk.position_sizing_engine import (
    PositionSizingEngine,
)


class LiveExecutionPipeline:

    def __init__(
        self,
        profile,
        symbol_map,
        *,
        mt5_module=mt5,
    ):
        self.profile = profile
        self.symbol_map = symbol_map
        self.mt5 = mt5_module

    def execute(self, plan):

        broker_symbol = resolve_broker_symbol(
            plan.symbol,
            self.symbol_map,
        )

        self.mt5.symbol_select(
            broker_symbol,
            True,
        )

        symbol_info = self.mt5.symbol_info(
            broker_symbol
        )

        tick = self.mt5.symbol_info_tick(
            broker_symbol
        )

        account_info = self.mt5.account_info()

        if symbol_info is None:
            raise RuntimeError(
                f"Cannot read symbol info for: "
                f"{broker_symbol}"
            )

        if tick is None:
            raise RuntimeError(
                f"Cannot read tick for: "
                f"{broker_symbol}"
            )

        if account_info is None:
            raise RuntimeError(
                "Cannot read MT5 account information."
            )

        order_type = plan.order_type.replace(
            " NOW",
            "",
        )

        market_order_types = {
            "BUY",
            "SELL",
        }

        pending_order_types = {
            "BUY LIMIT",
            "SELL LIMIT",
            "BUY STOP",
            "SELL STOP",
        }

        if order_type not in (
            market_order_types
            | pending_order_types
        ):
            raise ValueError(
                f"Unsupported order type: "
                f"{order_type}"
            )

        if order_type == "BUY":
            price = tick.ask

        elif order_type == "SELL":
            price = tick.bid

        else:
            if plan.entry is None:
                raise ValueError(
                    "Pending order requires "
                    "an entry price."
                )

            price = plan.entry

        digits = symbol_info.digits
        point = symbol_info.point

        min_stop_distance = max(
            symbol_info.trade_stops_level * point,
            10 * point,
        )

        is_buy_order = order_type in {
            "BUY",
            "BUY LIMIT",
            "BUY STOP",
        }

        if is_buy_order:
            sl = min(
                plan.sl,
                price - min_stop_distance,
            )

            tp = max(
                plan.tp,
                price + min_stop_distance,
            )

        else:
            sl = max(
                plan.sl,
                price + min_stop_distance,
            )

            tp = min(
                plan.tp,
                price - min_stop_distance,
            )

        price = round(
            price,
            digits,
        )

        sl = round(
            sl,
            digits,
        )

        tp = round(
            tp,
            digits,
        )

        sizing_result = (
            PositionSizingEngine().evaluate(
                account_equity=float(
                    account_info.equity
                ),
            )
        )

        if not sizing_result.approved:
            raise RuntimeError(
                "Trade rejected by Stable Lot Policy: "
                f"{sizing_result.reason}"
            )

        lot = sizing_result.volume

        ExecutionValidator().validate(
            symbol=broker_symbol,
            volume=lot,
            order_type=order_type,
            price=price,
            sl=sl,
            tp=tp,
        )

        request = MT5OrderBuilder(
            mt5_module=self.mt5,
        ).build(
            symbol=broker_symbol,
            volume=lot,
            order_type=order_type,
            price=price,
            sl=sl,
            tp=tp,
            comment=plan.comment,
        )

        order_result = MT5Sender(
            mt5_module=self.mt5,
        ).send(
            request
        )

        if not order_result.success:
            raise RuntimeError(
                f"MT5 order failed: "
                f"retcode={order_result.retcode}, "
                f"comment={order_result.comment}"
            )

        organizational_id = (
            trade_id_generator.next_id()
        )

        if order_type in pending_order_types:
            return PendingOrderRecordBuilder().build(
                pending_order_id=organizational_id,
                symbol=plan.symbol,
                order_type=order_type,
                volume=lot,
                entry=price,
                sl=sl,
                tp=tp,
                order_result=order_result,
            )

        return TradeRecordBuilder().from_order_result(
            trade_id=organizational_id,
            symbol=plan.symbol,
            action=order_type,
            volume=lot,
            order_result=order_result,
        )