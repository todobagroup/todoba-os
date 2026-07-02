from collections import deque


class TaskQueue:
    def __init__(self):
        self._queue = deque()

    def add(self, task_id: str):
        self._queue.append(task_id)

    def next_task(self):
        if not self._queue:
            return None

        return self._queue[0]

    def remove(self, task_id: str):
        try:
            self._queue.remove(task_id)
        except ValueError:
            pass

    def size(self):
        return len(self._queue)


task_queue = TaskQueue()