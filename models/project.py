from pydantic import BaseModel, validator, Field
from enum import Enum
from datetime import datetime
from typing import List, Optional
from .user import User 

# --- Project Status Enum ---
class ProjectStatus(str, Enum):
    open = 'open'
    in_progress = 'in_progress'
    completed = 'completed'
    rejected = 'rejected'

# --- Rating Models ---
class RatingCreate(BaseModel):
    # [資安防護] 使用 Field 強制限制數值範圍 (ge=1, le=5)
    # 如果駭客傳送 100，Pydantic 會在進入路由前直接攔截並拋出錯誤
    score_dim1: int = Field(..., ge=1, le=5, description="評分必須在 1-5 之間")
    score_dim2: int = Field(..., ge=1, le=5, description="評分必須在 1-5 之間")
    score_dim3: int = Field(..., ge=1, le=5, description="評分必須在 1-5 之間")
    comment: str | None = None

class Rating(BaseModel):
    id: int
    from_user_id: int
    to_user_id: int
    score_dim1: int
    score_dim2: int
    score_dim3: int
    comment: str | None = None
    created_at: datetime
    
    class Config:
        from_attributes = True
        orm_mode = True

# --- Issue Models ---
class IssueCommentCreate(BaseModel):
    content: str

class IssueComment(BaseModel):
    id: int
    user_id: int
    content: str
    created_at: datetime
    sender: User
    
    class Config:
        from_attributes = True
        orm_mode = True

class IssueCreate(BaseModel):
    title: str

class Issue(BaseModel):
    id: int
    project_id: int
    title: str
    status: str 
    created_by_id: int
    created_at: datetime
    comments: List[IssueComment] = []
    creator: User
    
    class Config:
        from_attributes = True
        orm_mode = True

# --- Project Models ---

class ProjectCreate(BaseModel):
    title: str
    description: str | None = None
    deadline: datetime | None = None 
    budget: float | None = None # [关键修正] 新增預算欄位

    # [修正] 針對 deadline 處理空字串
    @validator('deadline', pre=True)
    def parse_deadline(cls, v):
        if isinstance(v, str):
            if v.strip() == "":
                return None
            # [新增] 手動解析 YYYY-MM-DD 格式，解決 Pydantic 422 錯誤
            try:
                return datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                pass # 如果格式不符，讓 Pydantic 嘗試預設解析
        return v

    # [修正] 針對 budget 處理空字串與逗號 (例如 "1,000")，避免 422 錯誤
    @validator('budget', pre=True)
    def parse_budget(cls, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str):
            cleaned_v = v.strip()
            if not cleaned_v:
                return None
            # 移除貨幣符號與逗號，讓 Pydantic 可以正確解析
            cleaned_v = cleaned_v.replace(",", "").replace("$", "").replace("NT", "").strip()
            try:
                return float(cleaned_v)
            except ValueError:
                return None
        return v

class Project(BaseModel):
    id: int
    client_id: int
    title: str
    description: str | None = None
    status: ProjectStatus
    deadline: datetime | None = None
    budget: float | None = None # [关键修正] 這裡也要加，回傳時才看得到
    created_at: datetime
    selected_contractor_id: int | None = None
    
    client: User 
    ratings: List[Rating] = []
    issues: List[Issue] = []
    
    class Config:
        from_attributes = True
        orm_mode = True

class ProjectUpdate(BaseModel):
    title: str
    description: str | None = None

class ProjectStatusUpdate(BaseModel):
    status: ProjectStatus
