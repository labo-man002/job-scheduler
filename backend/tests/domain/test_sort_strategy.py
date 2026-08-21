


import pytest

from app.domain.sort_strategy import FifoSort, PrioritySort, SortStrategy
from app.enums.priority import Priority
from tests.factories import  make_job


def test_fifo_sort_preserves_order():

  job1 = make_job(1,Priority.LOW)
  job2= make_job(2,Priority.URGENT)
  job3= make_job(3,Priority.HIGH)

  jobs = [job1, job2, job3]


  sortStrategy = FifoSort()
  result = sortStrategy.sort(jobs)
#   print(sortStrategy.sort(jobs)[0].priority)
  assert result == [job1, job2, job3]


def test_fifo_sort_does_not_modify_original_queue():
    job1 = make_job(1,Priority.LOW)
    job2 = make_job(2,Priority.HIGH)

    jobs = [job1, job2]

    original_queue = list(jobs)
  
    result = FifoSort().sort(jobs)

    # print(original_queue)
    # print(result)

    assert jobs == original_queue
    assert result is not jobs


def test_priority_sort():
    jobs = [
        make_job(1,Priority.LOW),
        make_job(2,Priority.URGENT),
        make_job(3,Priority.NORMAL),
        make_job(4,Priority.HIGH),
    ]

    strategy = PrioritySort()

    result = strategy.sort(jobs)

    print(result)
    
    assert [job.priority for job in result] == [
        Priority.URGENT,
        Priority.HIGH,
        Priority.NORMAL,
        Priority.LOW,
    ]

def test_priority_sort_key():
    strategy = PrioritySort()

    assert strategy.key(make_job(1,Priority.URGENT)) == 0
    assert strategy.key(make_job(2,Priority.HIGH)) == 1
    assert strategy.key(make_job(3,Priority.NORMAL)) == 2
    assert strategy.key(make_job(4,Priority.LOW)) == 3

def test_priority_sort_rejects_invalid_priority():
    job = make_job(1,"Priority.Invalid")

    strategy = PrioritySort()

    with pytest.raises(ValueError):
        strategy.sort([job])


def test_priority_sort_preserves_fifo_for_same_priority():
    job1 = make_job(1,Priority.HIGH)
    job2 = make_job(2,Priority.HIGH)
    job3 = make_job(3,Priority.HIGH)

    jobs = [job1, job2, job3]

    strategy = PrioritySort()

    result = strategy.sort(jobs)

    assert result == [job1, job2, job3]