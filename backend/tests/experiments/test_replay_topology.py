from pathlib import Path

import pytest
from pydantic import ValidationError

from app.experiments.replay import run_replay
from app.experiments.replay_input import Scenario

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "queue-replay"


@pytest.fixture
def fabric():
    return Scenario.model_validate_json((EXAMPLES / "leaf-spine.json").read_bytes())


@pytest.mark.parametrize("policy", ["fifo", "priority"])
def test_fabric_prefers_same_leaf_and_can_span_leaves_when_required(fabric, policy):
    result = run_replay(fabric, policy)
    same_leaf, cross_leaf, infeasible = result["jobs"]

    assert same_leaf["node_ids"] == [1, 3]
    assert same_leaf["leaf_ids"] == [1]
    assert same_leaf["cross_leaf"] is False
    assert same_leaf["finish"] - same_leaf["start"] == 4
    assert cross_leaf["leaf_ids"] == [1, 2]
    assert len(cross_leaf["node_ids"]) == 3
    assert cross_leaf["cross_leaf"] is True
    assert cross_leaf["wait"] == 3
    assert cross_leaf["finish"] - cross_leaf["start"] == 3
    assert infeasible["reason"] == "cannot_fit_empty_cluster"
    assert result["metrics"]["cross_leaf_placements"] == 1
    assert result["metrics"]["allocated_gpu_ticks"] == 17


def test_disconnected_fabric_rejects_capacity_that_cannot_form_a_bundle(fabric):
    payload = fabric.model_dump(mode="json")
    payload["topology"]["uplinks"].pop()
    result = run_replay(Scenario.model_validate(payload), "fifo")

    assert result["jobs"][0]["node_ids"] == [1, 3]
    assert result["jobs"][1]["reason"] == "no_connected_allocation"
    assert result["jobs"][2]["reason"] == "cannot_fit_empty_cluster"
    assert result["metrics"]["completed"] == 1
    assert result["metrics"]["cross_leaf_placements"] == 0


def test_same_workload_on_linear_topology_preserves_legacy_placement(fabric):
    payload = fabric.model_dump(mode="json")
    payload["topology"] = {"kind": "linear"}
    explicit = Scenario.model_validate(payload)
    payload["schema_version"] = 1
    payload.pop("topology")
    legacy = Scenario.model_validate(payload)

    result = run_replay(explicit, "fifo")
    assert run_replay(legacy, "fifo") == result
    assert result["jobs"][0]["node_ids"] == [1, 2]
    assert result["jobs"][0]["cross_leaf"] is None
    assert result["jobs"][1]["finish"] == 7
    assert result["metrics"]["cross_leaf_placements"] is None


@pytest.mark.parametrize(
    ("topology_changes", "message"),
    [
        ({"leaves": [1, 1]}, "leaf IDs must be unique"),
        ({"uplinks": [{"leaf": 3, "spine": 1}]}, "declared leaf"),
        ({"uplinks": [{"leaf": 1, "spine": 1}, {"leaf": 1, "spine": 1}]}, "uplinks must be unique"),
        ({"attachments": [{"node": 1, "leaf": 1}, {"node": 1, "leaf": 2}]}, "each node must be attached once"),
        ({"attachments": [{"node": 12, "leaf": 1}]}, "exactly the scenario node IDs"),
    ],
)
def test_fabric_rejects_ambiguous_or_unknown_endpoints(fabric, topology_changes, message):
    payload = fabric.model_dump(mode="json")
    payload["topology"].update(topology_changes)
    with pytest.raises(ValidationError, match=message):
        Scenario.model_validate(payload)


@pytest.mark.parametrize(
    ("version", "topology", "message"),
    [
        (1, {"kind": "linear"}, "explicit topology requires schema_version 2"),
        (2, None, "schema_version 2 requires a topology"),
    ],
)
def test_topology_requires_explicit_version(fabric, version, topology, message):
    payload = {**fabric.model_dump(mode="json"), "schema_version": version, "topology": topology}
    with pytest.raises(ValidationError, match=message):
        Scenario.model_validate(payload)
