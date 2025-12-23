from pydantic import BaseModel, EmailStr
from enum import Enum

# --- Pydantic Models ---

# Enum 必須和 db/models.py 中的 Enum 一致
class UserRole(str, Enum):
    client = 'client'
    contractor = 'contractor'

# 用於 API "回傳" 的 User (不包含密碼)
class User(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: UserRole
    average_rating: float = 0.0
    rating_count: int = 0

    class Config:
        from_attributes = True  # 允許 Pydantic 從 SQLAlchemy 物件讀取資料
        orm_mode = True

# 用於 API "輸入" (建立 User)
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole

# models/user.py
class UserLogin(BaseModel):
    username: str
    password: str    