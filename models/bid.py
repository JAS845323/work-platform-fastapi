from pydantic import BaseModel
from datetime import datetime
from .user import User

# 用於 API "輸入" (建立投標)
# 注意：實際 API 接收時會用 Form(...)，這個 Model 主要用於文件或內部驗證
class BidCreate(BaseModel):
    bid_amount: float
    proposal_text: str | None = None

# 用於 API "回傳" (顯示投標)
class Bid(BaseModel):
    id: int
    project_id: int
    contractor_id: int
    bid_amount: float
    proposal_text: str | None = None
    proposal_file_path: str | None = None # [延伸一] PDF 路徑
    created_at: datetime
    
    contractor: User 
    
    class Config:
        from_attributes = True