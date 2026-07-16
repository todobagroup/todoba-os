import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.broker.mt5_order_builder import MT5OrderBuilder


def print_result(order_type):

    builder = MT5OrderBuilder()

    request = builder.build(
        symbol="GOLD.i#",
        volume=0.01,
        order_type=order_type,
        price=3335.50,
        sl=3330.00,
        tp=3345.00,
    )

    print(f"\n=== {order_type} ===")

    print(request)

    print(request["symbol"] == "GOLD.i#")

    print(request["volume"] == 0.01)

    print(request["type"] is not None)

    print(request["action"] is not None)

    print(request["type_filling"] is not None)


def main():

    print("=== MT5 ORDER BUILDER TEST ===")

    for order_type in (
        "BUY",
        "SELL",
        "BUY LIMIT",
        "SELL LIMIT",
        "BUY STOP",
        "SELL STOP",
    ):
        print_result(order_type)


if __name__ == "__main__":
    main()