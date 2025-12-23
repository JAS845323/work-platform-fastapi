from pydantic import BaseModel
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
    score_dim1: int
    score_dim2: int
    score_dim3: int
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
