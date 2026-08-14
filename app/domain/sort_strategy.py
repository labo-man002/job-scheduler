"""Queue ordering strategies used by Scheduler."""

from abc import ABC, abstractmethod

from app.enums.priority import Priority


class SortStrategy(ABC):
    """Return jobs in the order in which the scheduler should consider them."""

    @abstractmethod
    def sort(self, queue):
        raise NotImplementedError


class PrioritySort(SortStrategy):
    """Urgent jobs first, with FIFO ordering for jobs at the same priority."""

    _rank = {
        Priority.URGENT: 0,
        Priority.HIGH: 1,
        Priority.NORMAL: 2,
        Priority.LOW: 3,
    }

    def sort(self, queue):
        try:
            return sorted(queue, key=lambda job: self._rank[job.priority])
        except KeyError as error:
            raise ValueError(f"Unsupported job priority: {error.args[0]!r}") from error


class FifoSort(SortStrategy):
    """Preserve enqueue order."""

    def sort(self, queue):
        return list(queue)
