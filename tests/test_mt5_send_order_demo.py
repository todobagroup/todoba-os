import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import MetaTrader5 as mt5

from backend.trading.broker.mt5_client import MT5Client
from backend.trading.broker.mt5_safety import MT5Safety
from backend.trading.broker.mt5_order_builder import MT5OrderBuilder
from backend.trading.broker.mt5_sender import MT5Sender


def main():

    print("=== MT5 DEMO SEND ORDER TEST ===")

    client = MT5Client()

    if not client.connect():
        print("Connect failed.")
        return

    MT5Safety().validate()

    symbol = "GOLD.i#"

    mt5.symbol_select(symbol, True)

    tick = mt5.symbol_info_tick(symbol)

    if tick is None:
        print("Cannot read tick.")
        client.disconnect()
        return

    price = tick.ask

    builder = MT5OrderBuilder()

    request = builder.build(
        symbol=symbol,
        volume=0.01,
        order_type="BUY",
        price=price,
        sl=price - 5,
        tp=price + 5,
        comment="TODOBA DEMO",
    )

    print("REQUEST:")
    print(request)

    sender = MT5Sender()

    result = sender.send(request)

    print("RESULT:")
    print(result)

    print("Order success:", result.success)

    client.disconnect()


if __name__ == "__main__":
    main()