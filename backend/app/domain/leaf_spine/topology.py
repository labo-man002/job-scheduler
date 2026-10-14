"""In-memory two-tier leaf/spine aggregate; canonical links and derived graph indexes.

No database or scheduler ownership: the topology models physical connections only.
"""

from dataclasses import replace
from heapq import heappop, heappush
from itertools import count
from math import isfinite

from .devices import GpuServer, Switch
from .link import Link, NetworkPath
from .types import (
    DeviceKind,
    DeviceRef,
    DeviceInUseError,
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


class LeafSpineTopology:
    """The only connection mutation gateway; external snapshots are immutable.

    Link records are canonical. _incident_links and _endpoint_link are derived
    lookup indexes, maintained atomically with registration and removal.
    """

    def __init__(self):
        self._switches: dict[str, Switch] = {}
        self._servers: dict[str, GpuServer] = {}
        self._node_server: dict[int, str] = {}
        self._links: dict[str, Link] = {}
        self._incident_links: dict[DeviceRef, set[str]] = {}
        self._endpoint_link: dict[EndpointRef, str] = {}
        self._next_link_id = 1

    def add_switch(self, switch: Switch) -> None:
        if not isinstance(switch, Switch):
            raise TypeError("expected Switch")
        if switch.id in self._switches:
            raise DuplicateIdError(f"switch {switch.id} already exists")
        self._switches[switch.id] = switch
        self._incident_links[DeviceRef(DeviceKind.SWITCH, switch.id)] = set()

    def add_server(self, server: GpuServer) -> None:
        if not isinstance(server, GpuServer):
            raise TypeError("expected GpuServer")
        if server.id in self._servers or server.node_id in self._node_server:
            raise DuplicateIdError(f"server ID {server.id} or mapped node {server.node_id} already exists")
        self._servers[server.id] = server
        self._node_server[server.node_id] = server.id
        self._incident_links[DeviceRef(DeviceKind.GPU_SERVER, server.id)] = set()

    def switches(self) -> tuple[Switch, ...]:
        return tuple(self._switches[key] for key in sorted(self._switches))

    def servers(self) -> tuple[GpuServer, ...]:
        return tuple(self._servers[key] for key in sorted(self._servers))

    def links(self) -> tuple[Link, ...]:
        return tuple(self._links[key] for key in sorted(self._links))

    def get_switch(self, switch_id: str) -> Switch:
        try:
            return self._switches[switch_id]
        except KeyError as exc:
            raise UnknownDeviceError(f"unknown switch {switch_id}") from exc

    def get_server(self, server_id: str) -> GpuServer:
        try:
            return self._servers[server_id]
        except KeyError as exc:
            raise UnknownDeviceError(f"unknown GPU server {server_id}") from exc

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

    def remove_server(self, server_id: str) -> None:
        ref = DeviceRef(DeviceKind.GPU_SERVER, server_id)
        server = self.get_server(server_id)
        if self._incident_links[ref]:
            raise DeviceInUseError(f"server {server_id} still has physical links")
        del self._servers[server_id]
        del self._node_server[server.node_id]
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
        if ref.device_kind == DeviceKind.GPU_SERVER:
            server = self._servers.get(ref.device_id)
            if server is None or ref.endpoint_id != "nic0":
                raise UnknownEndpointError(f"unknown server NIC {ref.device_id}.{ref.endpoint_id}")
            return server.nic.capacity_gbps, server.nic.state
        raise UnknownEndpointError(f"unsupported device kind {ref.device_kind}")

    def _link_kind(self, a: EndpointRef, b: EndpointRef) -> LinkKind:
        if a.device_kind == b.device_kind == DeviceKind.SWITCH:
            roles = {self._switches[a.device_id].role, self._switches[b.device_id].role}
            if roles == {SwitchRole.LEAF, SwitchRole.SPINE}:
                return LinkKind.LEAF_SPINE
        elif {a.device_kind, b.device_kind} == {DeviceKind.SWITCH, DeviceKind.GPU_SERVER}:
            switch_ref = a if a.device_kind == DeviceKind.SWITCH else b
            if self._switches[switch_ref.device_id].role == SwitchRole.LEAF:
                return LinkKind.SERVER_LEAF
        raise InvalidConnectionError(f"invalid two-tier connection: {a} <-> {b}")

    def add_link(
        self, a: EndpointRef, b: EndpointRef, *, capacity_gbps: float,
        latency_us: float, link_id: str | None = None,
    ) -> Link:
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

    def set_server_state(self, server_id: str, state: OperationalState) -> None:
        self._require_state(state)
        self._servers[server_id] = replace(self.get_server(server_id), state=state)

    def set_nic_state(self, server_id: str, state: OperationalState) -> None:
        self._require_state(state)
        self._servers[server_id] = replace(self.get_server(server_id), nic_state=state)

    def _operational(self, link: Link) -> bool:
        if link.state != OperationalState.UP:
            return False
        for endpoint in (link.a, link.b):
            _, state = self._resolve_endpoint(endpoint)
            if state != OperationalState.UP:
                return False
            if endpoint.device_kind == DeviceKind.SWITCH:
                if self._switches[endpoint.device_id].state != OperationalState.UP:
                    return False
            elif self._servers[endpoint.device_id].state != OperationalState.UP:
                return False
        return True

    def get_neighbors(self, switch_id: str, *, operational_only: bool = False) -> tuple[str, ...]:
        self.get_switch(switch_id)
        ref = DeviceRef(DeviceKind.SWITCH, switch_id)
        neighbors = set()
        for link_id in self._incident_links[ref]:
            link = self._links[link_id]
            if link.kind != LinkKind.LEAF_SPINE or (operational_only and not self._operational(link)):
                continue
            other = link.b.device if link.a.device == ref else link.a.device
            neighbors.add(other.device_id)
        return tuple(sorted(neighbors))

    def connected_servers(self, leaf_id: str, *, operational_only: bool = False) -> tuple[str, ...]:
        switch = self.get_switch(leaf_id)
        if switch.role != SwitchRole.LEAF:
            raise InvalidConnectionError("connected_servers requires a LEAF switch")
        ref = DeviceRef(DeviceKind.SWITCH, leaf_id)
        servers = set()
        for link_id in self._incident_links[ref]:
            link = self._links[link_id]
            if link.kind != LinkKind.SERVER_LEAF or (operational_only and not self._operational(link)):
                continue
            other = link.b.device if link.a.device == ref else link.a.device
            servers.add(other.device_id)
        return tuple(sorted(servers))

    def find_path(
        self, root_switch_id: str, target_server_id: str, *,
        min_link_capacity_gbps: float | None = None, max_total_latency_us: float | None = None,
    ) -> NetworkPath | None:
        self.get_switch(root_switch_id)
        self.get_server(target_server_id)
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
        target = DeviceRef(DeviceKind.GPU_SERVER, target_server_id)
        if self.get_switch(root_switch_id).state != OperationalState.UP or self.get_server(target_server_id).state != OperationalState.UP:
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
                if other.kind == DeviceKind.GPU_SERVER and other != target:
                    continue  # servers are terminal, never transit devices
                new_lat = latency + link.latency_us
                if max_total_latency_us is not None and new_lat > max_total_latency_us:
                    continue
                key = (new_lat, hops + 1, links + (link.id,))
                if key < best.get(other, (float("inf"), float("inf"), ())):
                    best[other] = key
                    heappush(heap, (*key, next(sequence), other, devices + (other,), min(bottleneck, link.capacity_gbps)))
        return None

    def validate_structure(self) -> tuple[str, ...]:
        """Nonfatal structural diagnostics (partial graphs are still legal)."""
        messages = []
        for switch in self.switches():
            if not self.get_neighbors(switch.id):
                messages.append(f"switch {switch.id} has no leaf-spine uplinks")
        for server in self.servers():
            ref = DeviceRef(DeviceKind.GPU_SERVER, server.id)
            if not self._incident_links[ref]:
                messages.append(f"GPU server {server.id} has no leaf attachment")
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
        assert self._node_server == {server.node_id: server.id for server in self._servers.values()}
