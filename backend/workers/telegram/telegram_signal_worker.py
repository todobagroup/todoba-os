"""
TODOBA Telegram Signal Worker

Receives Telegram signals and sends them
to TODOBA Signal Gateway.
"""

from backend.workers.worker import Worker


class TelegramSignalWorker(Worker):

    def __init__(self, gateway):
        self.gateway = gateway
        self.running = False


    def start(self):

        self.running = True

        return True


    def stop(self):

        self.running = False

        return True


    def execute(self, task):

        if not self.running:
            raise RuntimeError("Worker is not running.")

        return self.gateway.receive(task)