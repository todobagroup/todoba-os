import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.lot_calculator import calculate


def main():

    print("=== LOT CALCULATOR TEST ===")

    lot = calculate("FIXED_001")

    print("Lot =", lot)

    print(lot == 0.01)


if __name__ == "__main__":
    main()