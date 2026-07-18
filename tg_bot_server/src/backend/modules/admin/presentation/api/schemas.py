from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1)


class AdminResponse(BaseModel):
    id: str
    email: str
    full_name: str
    status: str
    last_login_at: str | None


class LoginResponse(BaseModel):
    admin: AdminResponse
    csrf_token: str
