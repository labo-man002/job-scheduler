<<<<<<< HEAD
<<<<<<< HEAD
from app.enums.basicEnum import BasicEnum


class ClientStatus(BasicEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
=======




from enum import Enum


class ClientStatus(Enum):
   
 ONLINE	="ONLINE"
 OFFLINE = "OFLINE"
>>>>>>> 1d3c52a (Start coding)
=======
from enum import Enum


class ClientStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
>>>>>>> 34ff04a (Align database models with ERD design)
