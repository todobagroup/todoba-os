"""
TODOBA Worker Interface

Base contract for all workers.
"""


from abc import ABC, abstractmethod


class Worker(ABC):
    """
    Base worker contract.
    """

    @abstractmethod
    def start(self):
        """
        Start worker.
        """
        pass


    @abstractmethod
    def stop(self):
        """
        Stop worker.
        """
        pass


    @abstractmethod
    def execute(self, task):
        """
        Execute assigned task.
        """
        pass