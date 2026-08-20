
from app.domain.place_algorithm import PackAlgorithm ,PlaceAlgorithm
from app.domain.placer import Placer
from app.domain.scheduler import Scheduler
from app.models.resourceNode import ResourceNode
from app.domain.topology import Topology
from app.enums.resourceStatus import ResourceStatus
from app.enums.nodeStatus import NodeStatus
from tests.factories import make_cluster, make_job, make_node
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

    placer = Placer([] ,algorithm =None ,topology=Topology)
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

def test_attempt_placement():
    job = make_job(1)

    nodes = [make_node(i, [i]) for i in range(8)]
    cluster = make_cluster(1, dimension=[8], wrap=True)

    topology = Topology(cluster)
    algorithm = PackAlgorithm()

    placer = Placer(nodes, algorithm, topology)
    scheduler = Scheduler(placer)

    result = scheduler.attempt_placement(job)


    assert result[0].resource_status == ResourceStatus.ALLOCATED

def test_release_node_marks_resources_unavailable_when_node_down():

    nodes = [make_node(i, [i]) for i in range(8)]

    cluster = make_cluster(1, dimension=[8], wrap=True)

    topology = Topology(cluster)
    algorithm = PackAlgorithm()

    placer = Placer(nodes, algorithm, topology)
    scheduler = Scheduler(placer)

    nodes[7].status = NodeStatus.DOWN

    scheduler.release_node(nodes[7])

    for resource in nodes[7].resources:
        assert resource.resource_status == ResourceStatus.UNAVAILABLE

    # print(scheduler.release_node(nodes[7]))