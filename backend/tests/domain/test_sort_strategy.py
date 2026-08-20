


from app.domain.sort_strategy import FifoSort, SortStrategy
from app.enums.priority import Priority
from tests.factories import  make_job


def test_fifo_sort():

  job1 = make_job(1,Priority.LOW)
  job2= make_job(1,Priority.URGENT)
  job3= make_job(1,Priority.HIGH)

  jobs = [job1, job2, job3]


  sortStrategy = FifoSort()
  result = sortStrategy.sort(jobs)
#   print(sortStrategy.sort(jobs)[0].priority)
  assert result == [job1, job2, job3]
