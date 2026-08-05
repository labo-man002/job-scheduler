


from enum import Enum


class EventType(Enum):
    JOB_SUBMITTED = "JOB_SUBMITTED"	
    JOB_Running	="JOB_Running"
    JOB_COMPLETED = "JOB_COMPLETED"	
    JOB_FAILED ="JOB_FAILED"