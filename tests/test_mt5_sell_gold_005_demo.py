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
    print("=== MT5 SELL GOLD 0.05 DEMO ===")

    client = MT5Client()

    if not client.connect():
        print("Connect failed.")
        return

    MT5Safety().validate()

    symbol = "GOLD.i#"
    mt5.symbol_select(symbol, True)

    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)

    if info is None or tick is None:
        print("Cannot read symbol info or tick.")
        client.disconnect()
        return

    price = round(tick.bid, info.digits)
    sl = round(price + 5, info.digits)
    tp = round(price - 5, info.digits)

    request = MT5OrderBuilder().build(
        symbol=symbol,
        volume=0.05,
        order_type="SELL",
        price=price,
        sl=sl,
        tp=tp,
        comment="TODOBA SELL DEMO",
    )

    print("REQUEST:")
    print(request)

    result = MT5Sender().send(request)

    print("RESULT:")
    print(result)
    print("Success:", result.success)

    client.disconnect()


if __name__ == "__main__":
    main()