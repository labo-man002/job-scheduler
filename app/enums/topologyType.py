

from sqlalchemy import Enum


class TopologyType(Enum):
    FAT_TREE = "FAT_TREE"
    DRAGON_FLY ="DRAGON_FLY"
    TORUS="TORUS"