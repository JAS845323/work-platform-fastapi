from pydantic import BaseModel
from datetime import datetime
from .user import User # 匯入 User 模型

# --- Pydantic Models ---

# 用於 API "輸入" (建立投標)
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
    created_at: datetime
    
    contractor: User # 巢狀模型：顯示是哪個接案人投的標
    
    class Config:
        from_attributes = True