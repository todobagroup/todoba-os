import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.models.order_result import OrderResult


def main():

    print("=== ORDER RESULT TEST ===")

    result = OrderResult(
        success=True,
        retcode=10009,
        order=123456,
        deal=654321,
        volume=0.01,
        price=3335.00,
        comment="Done",
    )

    print(result)

    print(result.success is True)
    print(result.volume == 0.01)
    print(result.price == 3335.00)


if __name__ == "__main__":
    main()