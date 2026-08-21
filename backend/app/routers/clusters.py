from fastapi import APIRouter, HTTPException

from app import schemas
from app.dependencies import DbDep
from app.domain.exceptions import ClusterNotFoundError
from app.domain.server import NodeSpec, ResourceCount, Server

router = APIRouter(prefix="/clusters", tags=["Clusters"])


def _node_out(node):
    return schemas.NodeOut(
        node_id=node.node_id,
        coordinates=node.coordinates,
        status=node.status,
        resources=[schemas.NodeResourceOut(**summary) for summary in node.resource_summary()],
    )


def _cluster_detail_out(cluster):
    return schemas.ClusterDetailOut(
        cluster_id=cluster.cluster_id,
        cluster_name=cluster.cluster_name,
        topology_type=cluster.topology_type,
        dimension=cluster.dimension,
        wrap=cluster.wrap,
        total_capacity=cluster.total_capacity(),
        free_capacity=cluster.free_capacity(),
        nodes=[_node_out(node) for node in cluster.nodes],
    )


@router.post("", response_model=schemas.ClusterDetailOut, status_code=201)
def create_cluster(payload: schemas.ClusterCreate, db: DbDep):
    server = Server(db)
    node_specs = [
        NodeSpec(
            coordinates=spec.coordinates,
            resources=[ResourceCount(resource_type=r.resource_type, count=r.count) for r in spec.resources],
        )
        for spec in payload.nodes
    ]
    try:
        cluster = server.create_cluster(
            cluster_name=payload.cluster_name,
            topology_type=payload.topology_type,
            dimension=payload.dimension,
            wrap=payload.wrap,
            node_specs=node_specs,
        )
        db.commit()
    except ValueError as error:  # bad topology/dimension/wrap shape, or a node's coordinates don't fit it
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error

    db.refresh(cluster)
    return _cluster_detail_out(cluster)


@router.get("", response_model=list[schemas.ClusterOut])
def list_clusters(db: DbDep):
    return [
        schemas.ClusterOut(
            cluster_id=cluster.cluster_id,
            cluster_name=cluster.cluster_name,
            topology_type=cluster.topology_type,
            dimension=cluster.dimension,
            wrap=cluster.wrap,
            total_capacity=cluster.total_capacity(),
            free_capacity=cluster.free_capacity(),
        )
        for cluster in Server(db).list_clusters()
    ]


@router.get("/{cluster_id}", response_model=schemas.ClusterDetailOut)
def get_cluster(cluster_id: int, db: DbDep):
    try:
        cluster = Server(db).get_cluster(cluster_id)
    except ClusterNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Cluster {error} not found") from error

    return _cluster_detail_out(cluster)


@router.get("/{cluster_id}/allocations", response_model=list[schemas.NodeAllocationOut])
def list_cluster_allocations(cluster_id: int, db: DbDep):
    return [
        schemas.NodeAllocationOut(
            node_id=an.resource_node.node_id,
            job_id=an.allocation.job_id,
            resource_type=an.resource_node.resource_type,
        )
        for an in Server(db).list_cluster_allocations(cluster_id)
    ]
