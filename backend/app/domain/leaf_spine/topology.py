"""In-memory two-tier leaf/spine aggregate; canonical links and derived graph indexes.

The topology owns switches and physical links, and references existing ORM Node
objects as compute/network endpoints. Node inventory and persistence remain
owned by the caller and SQLAlchemy session.
"""

from dataclasses import replace
from heapq import heappop, heappush
from itertools import count
from math import isfinite

from app.enums import NodeStatus
from app.models.node import Node

from ..topology import PlacementTopology, PlacementTopologyView
from .devices import Switch
from .link import Link, NetworkPath
from .types import (
    DeviceInUseError,
    DeviceKind,
    DeviceRef,
    DuplicateIdError,
    EndpointOccupiedError,
    EndpointRef,
    InvalidConnectionError,
    InvalidLinkPropertiesError,
    LinkKind,
    OperationalState,
    SwitchRole,
    UnknownDeviceError,
    UnknownEndpointError,
    UnknownLinkError,
)
from ..topology import PlacementTopology, PlacementTopologyView


class LeafSpineTopology(PlacementTopology):
    """The only connection mutation gateway; Node identity is shared with ORM.

    Link records are canonical. _incident_links and _endpoint_link are derived
    lookup indexes, maintained atomically with registration and removal.
    The caller owns Node lifecycle and state changes; this class never mutates
    Node or ResourceNode objects.
    """

    def __init__(self):
        self._switches: dict[str, Switch] = {}
        self._nodes: dict[str, Node] = {}
        self._links: dict[str, Link] = {}
        self._incident_links: dict[DeviceRef, set[str]] = {}
        self._endpoint_link: dict[EndpointRef, str] = {}
        self._next_link_id = 1

    def build_view(self, nodes: list[Node]) -> "LeafSpineTopologyView":
        return LeafSpineTopologyView(self, nodes)

    def add_switch(self, switch: Switch) -> None:
        if not isinstance(switch, Switch):
            raise TypeError("expected Switch")
        if switch.id in self._switches:
            raise DuplicateIdError(f"switch {switch.id} already exists")
        self._switches[switch.id] = switch
        self._incident_links[DeviceRef(DeviceKind.SWITCH, switch.id)] = set()

    def add_node(self, node: Node) -> None:
        """Register the existing ORM Node as its own network endpoint."""
        if not isinstance(node, Node):
            raise TypeError("expected Node")
        if type(node.node_id) is not int or node.node_id < 0:
            raise ValueError("Node must have a persisted nonnegative node_id")
        node_key = str(node.node_id)
        if node_key in self._nodes:
            raise DuplicateIdError(f"Node {node.node_id} is already registered")
        self._nodes[node_key] = node
        self._incident_links[DeviceRef(DeviceKind.NODE, node_key)] = set()

    def switches(self) -> tuple[Switch, ...]:
        return tuple(self._switches[key] for key in sorted(self._switches))

    def nodes(self) -> tuple[Node, ...]:
        return tuple(self._nodes[key] for key in sorted(self._nodes, key=int))

    def links(self) -> tuple[Link, ...]:
        return tuple(self._links[key] for key in sorted(self._links))

    def get_switch(self, switch_id: str) -> Switch:
        try:
            return self._switches[switch_id]
        except KeyError as exc:
            raise UnknownDeviceError(f"unknown switch {switch_id}") from exc

    def get_node(self, node_id: int) -> Node:
        if type(node_id) is not int or node_id < 0:
            raise UnknownDeviceError(f"invalid Node ID {node_id}")
        try:
            return self._nodes[str(node_id)]
        except KeyError as exc:
            raise UnknownDeviceError(f"unknown Node {node_id}") from exc

    def get_link(self, link_id: str) -> Link:
        try:
            return self._links[link_id]
        except KeyError as exc:
            raise UnknownLinkError(f"unknown link {link_id}") from exc

    def remove_switch(self, switch_id: str) -> None:
        ref = DeviceRef(DeviceKind.SWITCH, switch_id)
        self.get_switch(switch_id)
        if self._incident_links[ref]:
            raise DeviceInUseError(f"switch {switch_id} still has physical links")
        del self._switches[switch_id]
        del self._incident_links[ref]

    def remove_node(self, node_id: int) -> None:
        ref = DeviceRef(DeviceKind.NODE, str(node_id))
        self.get_node(node_id)
        if self._incident_links[ref]:
            raise DeviceInUseError(f"Node {node_id} still has physical links")
        del self._nodes[str(node_id)]
        del self._incident_links[ref]

    def _resolve_endpoint(self, ref: EndpointRef) -> tuple[float, OperationalState]:
        if not isinstance(ref, EndpointRef):
            raise UnknownEndpointError("endpoint must be an EndpointRef")
        if ref.device_kind == DeviceKind.SWITCH:
            switch = self._switches.get(ref.device_id)
            if switch is None:
                raise UnknownEndpointError(f"unknown switch {ref.device_id}")
            if not ref.endpoint_id.startswith("p") or not ref.endpoint_id[1:].isdecimal():
                raise UnknownEndpointError(f"invalid port identity {ref.endpoint_id}")
            number = int(ref.endpoint_id[1:])
            if ref.endpoint_id != f"p{number}":
                raise UnknownEndpointError(f"noncanonical port identity {ref.endpoint_id}")
            try:
                port = switch.get_port(number)
            except ValueError as exc:
                raise UnknownEndpointError(f"unknown port {ref.endpoint_id} on {switch.id}") from exc
            return port.capacity_gbps, port.state
        if ref.device_kind == DeviceKind.NODE:
            node = self._nodes.get(ref.device_id)
            if node is None or ref.endpoint_id != "nic0" or node.nic_capacity_gbps is None:
                raise UnknownEndpointError(f"unknown or unconfigured Node NIC {ref.device_id}.{ref.endpoint_id}")
            return node.nic_capacity_gbps, node.nic_state
        raise UnknownEndpointError(f"unsupported device kind {ref.device_kind}")

    def _link_kind(self, a: EndpointRef, b: EndpointRef) -> LinkKind:
        if a.device_kind == b.device_kind == DeviceKind.SWITCH:
            roles = {self._switches[a.device_id].role, self._switches[b.device_id].role}
            if roles == {SwitchRole.LEAF, SwitchRole.SPINE}:
                return LinkKind.LEAF_SPINE
        elif {a.device_kind, b.device_kind} == {DeviceKind.SWITCH, DeviceKind.NODE}:
            switch_ref = a if a.device_kind == DeviceKind.SWITCH else b
            if self._switches[switch_ref.device_id].role == SwitchRole.LEAF:
                return LinkKind.NODE_LEAF
        raise InvalidConnectionError(f"invalid two-tier connection: {a} <-> {b}")

    def validate_connection(
        self, a: EndpointRef, b: EndpointRef, *, capacity_gbps: float,
        latency_us: float, link_id: str | None = None,
    ) -> LinkKind:
        """Validate a proposed physical connection without changing the topology."""
        if a == b:
            raise InvalidConnectionError("an endpoint cannot connect to itself")
        cap_a, _ = self._resolve_endpoint(a)
        cap_b, _ = self._resolve_endpoint(b)
        kind = self._link_kind(a, b)
        if a in self._endpoint_link or b in self._endpoint_link:
            raise EndpointOccupiedError("physical endpoint already connected (including DOWN links)")
        if (
            not isinstance(capacity_gbps, (int, float)) or isinstance(capacity_gbps, bool)
            or not isfinite(capacity_gbps) or not 0 < capacity_gbps <= min(cap_a, cap_b)
        ):
            raise InvalidLinkPropertiesError("link capacity must be finite, positive and within both endpoint ratings")
        if (
            not isinstance(latency_us, (int, float)) or isinstance(latency_us, bool)
            or not isfinite(latency_us) or latency_us < 0
        ):
            raise InvalidLinkPropertiesError("link latency must be finite and nonnegative")
        if link_id is not None and (not isinstance(link_id, str) or not link_id.strip()):
            raise InvalidLinkPropertiesError("link ID must be nonempty")
        if link_id in self._links:
            raise DuplicateIdError(f"link {link_id} already exists")
        return kind

    def add_link(
        self, a: EndpointRef, b: EndpointRef, *, capacity_gbps: float,
        latency_us: float, link_id: str | None = None,
    ) -> Link:
        kind = self.validate_connection(
            a, b, capacity_gbps=capacity_gbps, latency_us=latency_us, link_id=link_id
        )
        generated = link_id is None
        if generated:
            while f"link-{self._next_link_id}" in self._links:
                self._next_link_id += 1
            link_id = f"link-{self._next_link_id}"
        link = Link(link_id, a, b, kind, capacity_gbps, latency_us)
        # The whole operation is a single domain mutation: rollback indexes on unexpected failure.
        try:
            self._links[link_id] = link
            self._endpoint_link[a] = link_id
            self._endpoint_link[b] = link_id
            self._incident_links[a.device].add(link_id)
            self._incident_links[b.device].add(link_id)
        except Exception:
            self._links.pop(link_id, None)
            self._endpoint_link.pop(a, None)
            self._endpoint_link.pop(b, None)
            self._incident_links[a.device].discard(link_id)
            self._incident_links[b.device].discard(link_id)
            raise
        if generated:
            self._next_link_id += 1
        return link

    def remove_link(self, link_id: str) -> None:
        link = self.get_link(link_id)
        del self._links[link_id]
        del self._endpoint_link[link.a]
        del self._endpoint_link[link.b]
        self._incident_links[link.a.device].remove(link_id)
        self._incident_links[link.b.device].remove(link_id)

    def find_link_by_endpoint(self, endpoint: EndpointRef) -> Link | None:
        self._resolve_endpoint(endpoint)
        link_id = self._endpoint_link.get(endpoint)
        return self._links[link_id] if link_id is not None else None

    def set_link_state(self, link_id: str, state: OperationalState) -> None:
        self._require_state(state)
        self._links[link_id] = replace(self.get_link(link_id), state=state)

    @staticmethod
    def _require_state(state: OperationalState) -> None:
        if not isinstance(state, OperationalState):
            raise ValueError("state must be an OperationalState")

    def set_switch_state(self, switch_id: str, state: OperationalState) -> None:
        self._require_state(state)
        self._switches[switch_id] = replace(self.get_switch(switch_id), state=state)

    def set_port_state(self, switch_id: str, port_number: int, state: OperationalState) -> None:
        self._require_state(state)
        self._switches[switch_id] = self.get_switch(switch_id).with_port_state(port_number, state)

    def _operational(self, link: Link) -> bool:
        if link.state != OperationalState.UP:
            return False
        for endpoint in (link.a, link.b):
            try:
                endpoint_capacity, state = self._resolve_endpoint(endpoint)
            except UnknownEndpointError:
                # A registered Node's NIC may have been reconfigured after
                # the physical link was added; that invalidates this path.
                return False
            if state != OperationalState.UP or link.capacity_gbps > endpoint_capacity:
                return False
            if endpoint.device_kind == DeviceKind.SWITCH:
                if self._switches[endpoint.device_id].state != OperationalState.UP:
                    return False
            elif self._nodes[endpoint.device_id].status == NodeStatus.DOWN:
                return False
        return True

    def get_neighbors(self, switch_id: str, *, operational_only: bool = False) -> tuple[tuple[str, Link], ...]:
        self.get_switch(switch_id)
        ref = DeviceRef(DeviceKind.SWITCH, switch_id)
        neighbors = []
        for link_id in self._incident_links[ref]:
            link = self._links[link_id]
            if link.kind != LinkKind.LEAF_SPINE or (operational_only and not self._operational(link)):
                continue
            other = link.b.device if link.a.device == ref else link.a.device
            neighbors.append((other.device_id, link))
        return tuple(sorted(neighbors, key=lambda neighbor: (neighbor[0], neighbor[1].id)))

    def connected_nodes(self, leaf_id: str, *, operational_only: bool = False) -> tuple[int, ...]:
        switch = self.get_switch(leaf_id)
        if switch.role != SwitchRole.LEAF:
            raise InvalidConnectionError("connected_nodes requires a LEAF switch")
        ref = DeviceRef(DeviceKind.SWITCH, leaf_id)
        node_ids = set()
        for link_id in self._incident_links[ref]:
            link = self._links[link_id]
            if link.kind != LinkKind.NODE_LEAF or (operational_only and not self._operational(link)):
                continue
            other = link.b.device if link.a.device == ref else link.a.device
            node_ids.add(int(other.device_id))
        return tuple(sorted(node_ids))

    def find_path(
        self, root_switch_id: str, target_node_id: int, *,
        min_link_capacity_gbps: float | None = None, max_total_latency_us: float | None = None,
    ) -> NetworkPath | None:
        self.get_switch(root_switch_id)
        self.get_node(target_node_id)
        if min_link_capacity_gbps is not None and (
            not isinstance(min_link_capacity_gbps, (int, float)) or isinstance(min_link_capacity_gbps, bool)
            or not isfinite(min_link_capacity_gbps) or min_link_capacity_gbps <= 0
        ):
            raise ValueError("min_link_capacity_gbps must be positive and finite")
        if max_total_latency_us is not None and (
            not isinstance(max_total_latency_us, (int, float)) or isinstance(max_total_latency_us, bool)
            or not isfinite(max_total_latency_us) or max_total_latency_us < 0
        ):
            raise ValueError("max_total_latency_us must be nonnegative and finite")
        root = DeviceRef(DeviceKind.SWITCH, root_switch_id)
        target = DeviceRef(DeviceKind.NODE, str(target_node_id))
        if self.get_switch(root_switch_id).state != OperationalState.UP or self.get_node(target_node_id).status == NodeStatus.DOWN:
            return None
        # Tie-break: (summed latency, hop count, lexicographic link-ID sequence).
        # Complete paths are query snapshots; no state is modified.
        sequence = count()
        heap = [(0.0, 0, (), next(sequence), root, (root,), float("inf"))]
        best: dict[DeviceRef, tuple[float, int, tuple[str, ...]]] = {root: (0.0, 0, ())}
        while heap:
            latency, hops, links, _, current, devices, bottleneck = heappop(heap)
            if best[current] != (latency, hops, links):
                continue
            if current == target:
                return NetworkPath(devices, links, latency, bottleneck)
            for link_id in sorted(self._incident_links[current]):
                link = self._links[link_id]
                if (min_link_capacity_gbps is not None and link.capacity_gbps < min_link_capacity_gbps) or not self._operational(link):
                    continue
                other = link.b.device if link.a.device == current else link.a.device
                if other.kind == DeviceKind.NODE and other != target:
                    continue  # compute nodes are terminal, never transit devices
                new_lat = latency + link.latency_us
                if max_total_latency_us is not None and new_lat > max_total_latency_us:
                    continue
                key = (new_lat, hops + 1, (*links, link.id))
                if key < best.get(other, (float("inf"), float("inf"), ())):
                    best[other] = key
                    heappush(
                        heap,
                        (*key, next(sequence), other, (*devices, other), min(bottleneck, link.capacity_gbps)),
                    )
        return None

    def find_node_path(
        self, source_node_id: int, target_node_id: int, *,
        min_link_capacity_gbps: float | None = None,
        max_total_latency_us: float | None = None,
    ) -> NetworkPath | None:
        """Find a deterministic operational path satisfying optional limits."""
        self.get_node(source_node_id)
        self.get_node(target_node_id)
        for value, name, allow_zero in (
            (min_link_capacity_gbps, "min_link_capacity_gbps", False),
            (max_total_latency_us, "max_total_latency_us", True),
        ):
            if value is not None and (
                not isinstance(value, (int, float)) or isinstance(value, bool)
                or not isfinite(value) or (value < 0 if allow_zero else value <= 0)
            ):
                qualifier = "nonnegative" if allow_zero else "positive"
                raise ValueError(f"{name} must be {qualifier} and finite")
        if source_node_id == target_node_id:
            return NetworkPath((DeviceRef(DeviceKind.NODE, str(source_node_id)),), (), 0.0, float("inf"))
        source = DeviceRef(DeviceKind.NODE, str(source_node_id))
        target = DeviceRef(DeviceKind.NODE, str(target_node_id))
        if self.get_node(source_node_id).status == NodeStatus.DOWN or self.get_node(target_node_id).status == NodeStatus.DOWN:
            return None
        sequence = count()
        heap = [(0.0, 0, (), next(sequence), source, (source,), float("inf"))]
        best = {source: (0.0, 0, ())}
        while heap:
            latency, hops, links, _, current, devices, bottleneck = heappop(heap)
            if best[current] != (latency, hops, links):
                continue
            if current == target:
                return NetworkPath(devices, links, latency, bottleneck)
            for link_id in sorted(self._incident_links[current]):
                link = self._links[link_id]
                if not self._operational(link):
                    continue
                if min_link_capacity_gbps is not None and link.capacity_gbps < min_link_capacity_gbps:
                    continue
                other = link.b.device if link.a.device == current else link.a.device
                if other.kind == DeviceKind.NODE and other != target:
                    continue
                new_latency = latency + link.latency_us
                if max_total_latency_us is not None and new_latency > max_total_latency_us:
                    continue
                key = (new_latency, hops + 1, (*links, link.id))
                if key < best.get(other, (float("inf"), float("inf"), ())):
                    best[other] = key
                    heappush(heap, (*key, next(sequence), other, (*devices, other), min(bottleneck, link.capacity_gbps)))
        return None
    def validate_structure(self) -> tuple[str, ...]:
        """Nonfatal structural diagnostics (partial graphs are still legal)."""
        messages = []
        for switch in self.switches():
            if not self.get_neighbors(switch.id):
                messages.append(f"switch {switch.id} has no leaf-spine uplinks")
        for node in self.nodes():
            ref = DeviceRef(DeviceKind.NODE, str(node.node_id))
            if not self._incident_links[ref]:
                messages.append(f"Node {node.node_id} has no leaf attachment")
        return tuple(messages)

    def _assert_indexes_consistent(self) -> None:
        """Internal test hook; rebuild expected indexes from canonical links."""
        incident = {ref: set() for ref in self._incident_links}
        endpoint_link = {}
        for link in self._links.values():
            assert link.a not in endpoint_link and link.b not in endpoint_link
            endpoint_link[link.a] = link.id
            endpoint_link[link.b] = link.id
            incident[link.a.device].add(link.id)
            incident[link.b.device].add(link.id)
        assert incident == self._incident_links
        assert endpoint_link == self._endpoint_link
        assert set(self._nodes) == {str(node.node_id) for node in self._nodes.values()}


class LeafSpineTopologyView(PlacementTopologyView):
    """Read-only adapter from a Leaf-Spine graph to the placement contract."""

    def __init__(self, topology: LeafSpineTopology, nodes: list[Node]):
        self.topology = topology
        supplied_by_id = {node.node_id: node for node in nodes}
        if len(supplied_by_id) != len(nodes):
            raise ValueError("placement inventory contains duplicate Node IDs")
        for node in nodes:
            if topology.get_node(node.node_id) is not node:
                raise ValueError(
                    f"placement Node {node.node_id} is not the registered Leaf-Spine Node instance"
                )
        # The view represents the physical fabric, not a per-job reservation
        # filter. Occupied/reserved Nodes remain visible for locality scoring.
        self._nodes = list(topology.nodes())

    @property
    def nodes(self) -> list[Node]:
        return self._nodes

    def is_reachable(self, a: Node, b: Node) -> bool:
        return self.topology.find_node_path(a.node_id, b.node_id) is not None

    def distance(self, a: Node, b: Node) -> float:
        path = self.topology.find_node_path(a.node_id, b.node_id)
        return path.total_latency_us if path is not None else float("inf")

    def path_latency(self, a: Node, b: Node) -> float | None:
        path = self.topology.find_node_path(a.node_id, b.node_id)
        return path.total_latency_us if path is not None else None

    def path_bandwidth(self, a: Node, b: Node) -> float | None:
        path = self.topology.find_node_path(a.node_id, b.node_id)
        return path.bottleneck_gbps if path is not None else None

    def path_metrics(
        self, a: Node, b: Node, *,
        min_bandwidth_gbps: float | None = None,
        max_latency_us: float | None = None,
    ) -> tuple[float, float] | None:
        path = self.topology.find_node_path(
            a.node_id, b.node_id,
            min_link_capacity_gbps=min_bandwidth_gbps,
            max_total_latency_us=max_latency_us,
        )
        return (path.total_latency_us, path.bottleneck_gbps) if path is not None else None
