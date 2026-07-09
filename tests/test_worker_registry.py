import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.workers.worker_registry import WorkerRegistry


class DemoWorker:
    pass


def main():

    print("=== WORKER REGISTRY TEST ===")

    registry = WorkerRegistry()

    worker = DemoWorker()

    registry.register("trade", worker)

    print(registry.get("trade") is worker)

    print(registry.get("content") is None)


if __name__ == "__main__":
    main()