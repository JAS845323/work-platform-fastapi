from pydantic import BaseModel
from enum import Enum
from datetime import datetime
from .user import User # 匯入我們之前定義的 User 模型

# --- Pydantic Models ---

# Enum 必須和 db/models.py 中的 Enum 一致
class ProjectStatus(str, Enum):
    open = 'open'
    in_progress = 'in_progress'
    completed = 'completed'
    rejected = 'rejected'

# 用於 API "輸入" (建立專案)
class ProjectCreate(BaseModel):
    title: str
    description: str | None = None # 允許描述為空

# 用於 API "回傳" (顯示專案詳細資料)
class Project(BaseModel):
    id: int
    client_id: int
    title: str
    description: str | None = None
    status: ProjectStatus
    created_at: datetime
    
    client: User # 巢狀模型：顯示建立此專案的委託人資料
    
    class Config:
        from_attributes = True # Pydantic V2 (取代 orm_mode)
 # 用於 API "輸入" (修改專案)
class ProjectUpdate(BaseModel):
    title: str
    description: str | None = None

# 用於 API "輸入" (結案管理：接受/退件)
class ProjectStatusUpdate(BaseModel):
    # 我們重複使用在 Project 模型頂部定義的 ProjectStatus Enum
    # 它只接受 'open', 'in_progress', 'completed', 'rejected'
    status: ProjectStatus