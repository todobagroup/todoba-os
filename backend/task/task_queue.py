"""
TODOBA Task Queue

Stores organizational tasks.
"""


class TaskQueue:

    def __init__(self):

        self._tasks = []


    def push(self, task):

        self._tasks.append(task)


    def pop(self):

        if not self._tasks:
            return None

        return self._tasks.pop(0)


    def size(self):

        return len(self._tasks)