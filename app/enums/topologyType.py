<<<<<<< HEAD
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
=======
from enum import Enum


class TopologyType(str, Enum):
<<<<<<< HEAD
    TORUS = "TORUS"
    MESH = "MESH"
    TREE = "TREE"
    FLAT = "FLAT"
>>>>>>> 34ff04a (Align database models with ERD design)
=======
    TORUS_3D = "TORUS_3D"
    TORUS_2D = "TORUS_2D"
    MESH_2D = "MESH_2D"
    FAT_TREE = "FAT_TREE"
  
>>>>>>> 4cfca51 (modifing and reviewing models and enum)
