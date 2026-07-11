import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.lifecycle.trade_record import TradeRecord
from backend.trading.lifecycle.trade_status import TradeStatus
from backend.trading.lifecycle.trade_experience_builder import (
    TradeExperienceBuilder,
)


def main():

    print("=== TRADE EXPERIENCE TEST ===")

    record = TradeRecord(
        trade_id="TRD-000001",
        symbol="GOLD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.CLOSED,
        order=123456,
        deal=654321,
    )

    experience = TradeExperienceBuilder().build(
        trade_record=record,
        outcome="WIN",
        reason="Take Profit Hit",
    )

    print(experience.trade_id)

    print(experience.outcome)

    print(experience.reason)


if __name__ == "__main__":
    main()