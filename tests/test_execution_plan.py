import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_plan import ExecutionPlan


def main():

    plan = ExecutionPlan(
        symbol="XAUUSD",
        order_type="BUY",
        entry=3320,
        sl=3310,
        tp=3340,
        lot=0.01,
        magic_number=10001,
        comment="TODOBA",
    )

    print(plan)

    print(plan.symbol == "XAUUSD")

    print(plan.lot == 0.01)

    print(plan.magic_number == 10001)


if __name__ == "__main__":
    main()