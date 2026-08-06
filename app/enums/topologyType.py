from enum import Enum


class TopologyType(str, Enum):
    TORUS = "TORUS"
    MESH = "MESH"
    TREE = "TREE"
    FLAT = "FLAT"
