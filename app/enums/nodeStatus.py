<<<<<<< HEAD
from app.enums.basicEnum import BasicEnum


class NodeStatus(BasicEnum):
    IDLE = "IDLE"
    ALLOCATED = "ALLOCATED"
    MIXED = "MIXED"
    DOWN = "DOWN"
=======



from enum import Enum


class NodeStatus(Enum):

    IDLE ="IDLE"	
    ALLOCATED ="ALLOCATED"	
    MIXED ="MIXED"	
    DOWN ="MIXED"	
 
>>>>>>> 1d3c52a (Start coding)
