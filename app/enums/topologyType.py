from enum import Enum


class TopologyType(str, Enum):
    TORUS_3D = "TORUS_3D"
    TORUS_2D = "TORUS_2D"
    MESH_2D = "MESH_2D"
    FAT_TREE = "FAT_TREE"
  