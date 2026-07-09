"""
TODOBA Worker Registry

Registers workers by task type.
"""


class WorkerRegistry:

    def __init__(self):

        self._workers = {}


    def register(self, task_type, worker):

        self._workers[task_type] = worker


    def get(self, task_type):

        return self._workers.get(task_type)