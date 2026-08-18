from app.domain.place_algorithm import PackAlgorithm
from app.domain.placer import Placer
from app.domain.scheduler import Scheduler
from tests.factories import make_job
import pytest

def test_enqueue_job():
    placer = Placer([] ,algorithm =None ,topology=None)
    scheduler = Scheduler(placer )
    job = make_job(1)

    scheduler.enqueue(job)

    assert job in scheduler._jobs
    assert scheduler._sequence ==1
    assert not scheduler.job_queue.empty()



def test_enqueue_duplicate_job():

    placer = Placer([] ,algorithm =None ,topology=None)
    scheduler = Scheduler(placer )
    job = make_job(1)

    scheduler.enqueue(job )

    with pytest.raises(ValueError):
        scheduler.enqueue(job )

def test_is_job_in_queue():

     placer = Placer([] ,algorithm =None ,topology=None)
     scheduler = Scheduler(placer )
     job = make_job(1)
    
     scheduler.enqueue(job)

     item = scheduler.job_queue.get()
    #  print(item[0][0])
    #  print(item[0][1])

    #  print(item[1])
    
     assert job == item[1]
     assert scheduler._sequence == item[0][1]
     assert scheduler.sort_strategy.key(job) == item[0][0]
     

def test_dequeue_job():

     placer = Placer([] ,algorithm =None ,topology=None)
     scheduler = Scheduler(placer )
     job = make_job(1)
     scheduler.enqueue(job)


     result = scheduler.dequeue()

     
     assert  job not  in scheduler._jobs
     assert  job == result

def test_dequeue_empty():

    placer = Placer([] ,algorithm =None ,topology=None)
    scheduler = Scheduler(placer )
    result = scheduler.dequeue()

    assert result is None
