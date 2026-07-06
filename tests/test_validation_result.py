import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.validation.validation_result import ValidationResult


def main():

    result = ValidationResult(
        passed=False,
        errors=[
            "Missing TP",
            "Unsupported Symbol"
        ]
    )

    print(result)

    print(result.passed is False)

    print(len(result.errors) == 2)


if __name__ == "__main__":
    main()