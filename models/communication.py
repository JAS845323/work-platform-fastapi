from pydantic import BaseModel
from datetime import datetime
from .user import User

# --- Pydantic Models ---

# 用於 API "輸入" (傳送訊息)
class MessageCreate(BaseModel):
    message: str

# 用於 API "回傳" (顯示訊息)
class Message(BaseModel):
    id: int
    project_id: int
    sender_id: int
    message: str
    created_at: datetime
    
    sender: User # 巢狀模型：顯示是誰傳的訊息
    
    class Config:
        from_attributes = True
        orm_mode = True