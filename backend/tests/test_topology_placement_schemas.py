import pytest
from pydantic import ValidationError

from app import schemas
from app.enums import ResourceType, TopologyType


def test_job_create_accepts_resource_requirements_and_optional_network_constraints():
    payload = schemas.JobCreate(
        client_id=1,
        duration=30,
        require_full_connectivity=True,
        min_bandwidth_gbps=100,
        max_latency_us=25,
        requirements=[{"resource_type": ResourceType.GPU, "amount": 4}],
    )

    assert payload.require_full_connectivity is True
    assert payload.min_bandwidth_gbps == 100
    assert payload.max_latency_us == 25


def test_job_create_rejects_node_count_fields():
    with pytest.raises(ValidationError):
        schemas.JobCreate(
            client_id=1,
            duration=30,
            min_nodes=2,
            max_nodes=3,
            requirements=[{"resource_type": ResourceType.GPU, "amount": 4}],
        )


def test_leaf_spine_cluster_schema_requires_graph_and_nic_metadata():
    payload = schemas.ClusterCreate(
        cluster_name="gpu-fabric",
        topology_type=TopologyType.LEAF_SPINE,
        nodes=[
            {
                "nic_capacity_gbps": 100,
                "resources": [{"resource_type": ResourceType.GPU, "count": 4}],
            }
        ],
        fabric={
            "switches": [
                {
                    "switch_id": "leaf-1",
                    "role": "LEAF",
                    "model": "demo",
                    "port_groups": [{"count": 1, "speed_gbps": 200}],
                }
            ],
            "links": [],
        },
    )

    assert payload.dimension == []
    assert payload.fabric.switches[0].switch_id == "leaf-1"


def test_leaf_spine_cluster_schema_rejects_grid_dimensions_and_missing_fabric():
    with pytest.raises(ValidationError):
        schemas.ClusterCreate(
            cluster_name="invalid",
            topology_type=TopologyType.LEAF_SPINE,
            dimension=[4],
            nodes=[{"nic_capacity_gbps": 100, "resources": [{"resource_type": ResourceType.GPU, "count": 1}]}],
        )
