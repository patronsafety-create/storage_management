from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    """فرمت استاندارد بازگرداندن توکن به کلاینت"""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """داده‌هایی که درون خود توکن (Payload) ذخیره می‌شوند"""
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    is_active: bool

    class Config:
        from_attributes = True