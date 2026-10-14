"""Read-only adapter tests: existing SQLAlchemy ResourceNode remains authoritative."""

import pytest

from app.domain.leaf_spine import (
    DeviceKind, EndpointRef, GpuCandidateFinder, GpuServer,
    InconsistentInventoryError, LeafSpineTopology, OperationalState,
    PortGroupConfig, Switch, SwitchHardwareConfig, SwitchRole,
)
from app.enums import NodeStatus, ResourceStatus, ResourceType
from tests.factories import make_node


def fabric():
    topo = LeafSpineTopology()
    cfg = SwitchHardwareConfig("demo", (PortGroupConfig(4, 200),))
    topo.add_switch(Switch("leaf", SwitchRole.LEAF, cfg))
    topo.add_server(GpuServer("gpu-a", 10, 100))
    topo.add_server(GpuServer("gpu-b", 11, 100))
    for i, sid in enumerate(("gpu-a", "gpu-b"), start=1):
        topo.add_link(
            EndpointRef(DeviceKind.SWITCH, "leaf", f"p{i}"),
            EndpointRef(DeviceKind.GPU_SERVER, sid, "nic0"),
            capacity_gbps=100, latency_us=i,
            link_id=f"access-{i}",
        )
    return topo


def test_candidate_discovery_filters_by_real_gpu_units_without_mutation():
    topo = fabric()
    n1 = make_node(10, [0], 3, ResourceType.GPU)
    n2 = make_node(11, [1], 3, ResourceType.GPU)
    n1.resources[0].resource_status = ResourceStatus.ALLOCATED
    n2.resources[0].resource_status = ResourceStatus.UNAVAILABLE
    n2.resources[1].resource_status = ResourceStatus.ALLOCATED
    snapshot = [(n.status, tuple(r.resource_status for r in n.resources)) for n in (n1, n2)]
    finder = GpuCandidateFinder(topo)
    candidates = finder.find_candidates("leaf", [n2, n1], min_free_gpus_per_server=2)
    assert len(candidates) == 1
    assert candidates[0].server_id == "gpu-a"
    assert candidates[0].free_gpu_ids == tuple(sorted(r.resource_node_id for r in n1.resources[1:]))
    assert candidates[0].free_gpu_count == 2
    assert snapshot == [(n.status, tuple(r.resource_status for r in n.resources)) for n in (n1, n2)]
    assert [c.server_id for c in finder.find_candidates("leaf", [n1, n2])] == ["gpu-a", "gpu-b"]
    assert finder.find_candidates("leaf", [n1, n2], min_link_capacity_gbps=101) == ()
    assert [c.server_id for c in finder.find_candidates("leaf", [n1, n2], max_total_latency_us=1)] == ["gpu-a"]
    topo.set_link_state("access-1", OperationalState.DOWN)
    assert finder.find_candidates("leaf", [n1, n2], min_free_gpus_per_server=2) == ()


def test_candidate_discovery_ignores_down_nodes():
    topo = fabric()
    nodes = [make_node(10, [0], 2, ResourceType.GPU, NodeStatus.DOWN),
             make_node(11, [1], 2, ResourceType.GPU)]
    assert [c.server_id for c in GpuCandidateFinder(topo).find_candidates("leaf", nodes)] == ["gpu-b"]


def test_candidate_discovery_rejects_mismatched_and_duplicate_inventory():
    topo = fabric()
    finder = GpuCandidateFinder(topo)
    one = make_node(10, [0], 2, ResourceType.GPU)
    with pytest.raises(InconsistentInventoryError):
        finder.find_candidates("leaf", [one])
    with pytest.raises(InconsistentInventoryError):
        finder.find_candidates("leaf", [one, one])
    with pytest.raises(ValueError):
        finder.find_candidates("leaf", [], min_free_gpus_per_server=0)
