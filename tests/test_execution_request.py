import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_request import ExecutionRequest


def main():

    request = ExecutionRequest(
        action="DEAL",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        price=None,
        sl=3310,
        tp=3340,
        deviation=20,
        magic_number=10001,
        comment="TODOBA",
    )

    print(request)

    print(request.action == "DEAL")

    print(request.volume == 0.01)

    print(request.comment == "TODOBA")


if __name__ == "__main__":
    main()