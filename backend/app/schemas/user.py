"""用户相关 schemas"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole


class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole = UserRole.OPERATOR
    department: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    department: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
