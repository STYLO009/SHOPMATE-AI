"""Auth request/response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.validators import validate_password


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    accept_terms: bool = False

    @field_validator("full_name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name is too short.")
        return v

    @field_validator("password")
    @classmethod
    def _strong_password(cls, v: str) -> str:
        err = validate_password(v)
        if err:
            raise ValueError(err)
        return v

    @field_validator("confirm_password")
    @classmethod
    def _match(cls, v: str, info) -> str:
        password = info.data.get("password")
        if password and v != password:
            raise ValueError("Passwords do not match.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember: bool = True


class UserOut(BaseModel):
    id: str
    full_name: str
    email: str
    profile_image_url: Optional[str] = None
    auth_provider: str
    email_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _strong_password(cls, v: str) -> str:
        err = validate_password(v)
        if err:
            raise ValueError(err)
        return v


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
