"""Queue management and placement orchestration.

Scheduler decides *when* a job is considered. It does not query or commit the
database; the server layer owns persistence. Placer decides *where* a selected
job runs.
"""

from queue import Empty, PriorityQueue

from .sort_strategy import FifoSort


class Scheduler:
    """Maintain a job queue and delegate placement of selected jobs.

    The queue stores the real job objects supplied by the caller. A caller
    normally uses ``dequeue()`` followed by ``attempt_placement(job)``; a job
    that cannot currently be placed can be enqueued again according to the
    caller's retry policy.
    """

    def __init__(
        self,
        placer,
        sort_strategy=None,
    ):
        self.placer = placer
        self.sort_strategy = sort_strategy or FifoSort()
        self.job_queue = PriorityQueue()
        self._jobs = []

    def set_sort_strategy(self, sort_strategy):
        """Change the strategy and immediately reorder the current queue."""
        self.sort_strategy = sort_strategy
        self._rebuild_queue()

    def enqueue(self, job):
        """Add a job to the queue, rejecting an accidental duplicate."""
        if any(queued.job_id == job.job_id for queued in self._jobs):
            raise ValueError(f"Job {job.job_id} is already queued")
        self._jobs.append(job)
   

    def dequeue(self):
        """Remove and return the next job, or ``None`` when the queue is empty."""
        try:
            job = self.job_queue.get()
        except Empty:
            return None
        self._jobs.remove(job)
        return job

    

    def attempt_placement(self, job):
        """Ask the configured placer to find resources for a selected job."""
        return self.placer.place(job)

    def release_node(self, node):
        """Release every resource on ``node`` through the configured placer."""
        self.placer.release_resource(list(node.resources))

    def _rebuild_queue(self):
        self.job_queue = PriorityQueue()
        for priority, job in enumerate(self.sort_strategy.sort(self._jobs)):
            self.job_queue.put((priority, job))
