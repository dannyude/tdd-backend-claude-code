from pydantic import BaseModel, ConfigDict


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    status: str
