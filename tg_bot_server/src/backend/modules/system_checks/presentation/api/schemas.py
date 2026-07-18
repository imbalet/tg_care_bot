from pydantic import BaseModel, Field


class CreateSystemCheckRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SystemCheckResponse(BaseModel):
    id: str
    name: str
    created_at: str
