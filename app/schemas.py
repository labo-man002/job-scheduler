from pydantic import BaseModel


class OurBaseModel(BaseModel):
    class Config:
        from_attributes = True


class BaseOut(OurBaseModel):
    detail: str
    status_code: int
