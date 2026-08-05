<<<<<<< HEAD
from app.enums.basicEnum import BasicEnum


class TopologyType(BasicEnum):
    RING = "RING"
    TORUS_3D = "TORUS_3D"
    TORUS_2D = "TORUS_2D"
    MESH_2D = "MESH_2D"
    FAT_TREE = "FAT_TREE"
  
=======


from sqlalchemy import Enum


class TopologyType(Enum):
    FAT_TREE = "FAT_TREE"
    DRAGON_FLY ="DRAGON_FLY"
    TORUS="TORUS"
>>>>>>> 1d3c52a (Start coding)
