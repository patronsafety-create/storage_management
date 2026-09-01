from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class RoleBase(BaseModel):
    name: str = Field(..., max_length=50, description="نام سیستمی نقش (مثل ADMIN)")
    description: Optional[str] = Field(None, max_length=200)
    permissions: List[str] = Field(default_factory=list, description="لیست دسترسی‌ها")
    is_active: bool = True

class RoleCreate(RoleBase):
    pass

class RoleResponse(RoleBase):
    id: int

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    username: str = Field(..., max_length=50)
    full_name: str = Field(..., max_length=100)
    telegram_id: Optional[str] = Field(None, max_length=50)
    is_active: bool = True
    role_id: int

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="رمز عبور خام که پیش از ذخیره هش خواهد شد")

class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    role: RoleResponse

    class Config:
        from_attributes = True