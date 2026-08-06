<<<<<<< HEAD
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
=======
from enum import Enum


class NodeStatus(str, Enum):
    IDLE = "IDLE"
    ALLOCATED = "ALLOCATED"
    MIXED = "MIXED"
    DOWN = "DOWN"
>>>>>>> 34ff04a (Align database models with ERD design)
