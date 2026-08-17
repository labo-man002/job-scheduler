"""Errors Server raises to signal a request can't be fulfilled -- routers
catch these by type and translate each into the appropriate HTTP status."""


class InstituteNotFoundError(Exception):
    pass


class ClientNotFoundError(Exception):
    pass


class ClusterNotFoundError(Exception):
    pass


class NodeNotFoundError(Exception):
    pass


class NodeNotInClusterError(Exception):
    def __init__(self, node_ids, cluster_id):
        self.node_ids = node_ids
        self.cluster_id = cluster_id
        super().__init__(f"node(s) {node_ids} are not in cluster {cluster_id}")


class ReservationConflictError(Exception):
    def __init__(self, node_ids):
        self.node_ids = node_ids
        super().__init__(f"node(s) {node_ids} already reserved by another institute for an overlapping period")


class ReservationNotFoundError(Exception):
    pass


class QuotaNotFoundError(Exception):
    pass


class JobNotFoundError(Exception):
    pass


class JobNotRunningError(Exception):
    pass


class JobTooLargeError(Exception):
    """No cluster, even fully empty, has enough capacity for this job --
    a rejection, not something waiting would ever resolve."""


class QuotaExceededError(Exception):
    def __init__(self, resource_type, limit):
        self.resource_type = resource_type
        self.limit = limit
        super().__init__(f"{resource_type} quota ({limit}) would be exceeded")
