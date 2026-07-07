import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.broker.broker_client import BrokerClient


def main():
    print("=== BROKER CLIENT TEST ===")

    print(hasattr(BrokerClient, "connect"))
    print(hasattr(BrokerClient, "disconnect"))
    print(hasattr(BrokerClient, "is_connected"))
    print(hasattr(BrokerClient, "execute"))


if __name__ == "__main__":
    main()