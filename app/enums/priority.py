<<<<<<< HEAD
<<<<<<< HEAD
from app.enums.basicEnum import BasicEnum


class Priority(BasicEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"
=======



from enum import Enum


class Priority(Enum):
  Low ="Low"
  High="High"
  Urgent ="Urgent"
  Normal = 'Normal'
>>>>>>> 1d3c52a (Start coding)
=======
from enum import Enum


class Priority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"
>>>>>>> 34ff04a (Align database models with ERD design)
