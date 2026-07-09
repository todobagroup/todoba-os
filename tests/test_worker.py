import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.workers.worker import Worker


class DemoWorker(Worker):

    def start(self):
        return True

    def stop(self):
        return True

    def execute(self, task):
        return task


def main():

    print("=== WORKER TEST ===")

    worker = DemoWorker()

    print(worker.start())

    print(worker.execute("BUY GOLD"))

    print(worker.stop())


if __name__ == "__main__":
    main()