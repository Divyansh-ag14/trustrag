import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    workspace_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    email: str
    name: str
    role: str

    model_config = {"from_attributes": True}
