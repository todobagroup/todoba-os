import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_validator import ExecutionValidator


def main():

    print("=== EXECUTION VALIDATION TEST ===")

    validator = ExecutionValidator()

    result = validator.validate(
        symbol="GOLD.i#",
        volume=0.01,
        order_type="BUY",
        price=3335.00,
        sl=3330.00,
        tp=3345.00,
    )

    print(result)

    print(result is True)


if __name__ == "__main__":
    main()