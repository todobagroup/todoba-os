"""
TODOBA Task Dispatcher

Dispatches tasks and records execution lifecycle.
"""

from datetime import datetime

from backend.task.task_status import TaskStatus


class TaskDispatcher:

    def __init__(self, queue, registry):

        self.queue = queue
        self.registry = registry


    def dispatch_next(self):

        task = self.queue.pop()

        if task is None:
            return None


        worker = self.registry.get(task.task_type)


        if worker is None:

            task.status = TaskStatus.FAILED

            raise ValueError(
                f"No worker registered for task type: {task.task_type}"
            )


        try:

            task.status = TaskStatus.RUNNING

            task.started_at = datetime.now()

            task.worker = worker.__class__.__name__


            result = worker.execute(task)


            task.result = result

            task.completed_at = datetime.now()

            task.status = TaskStatus.COMPLETED


            return result


        except Exception:

            task.status = TaskStatus.FAILED

            task.completed_at = datetime.now()

            raise