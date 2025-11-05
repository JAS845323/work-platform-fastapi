from passlib.context import CryptContext

# 設定密碼雜湊的演算法為 bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 驗證密碼
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# 取得密碼的雜湊值
def get_password_hash(password):
    return pwd_context.hash(password)
# auth/security.py

# ... (你原有的 pwd_context, verify_password, get_password_hash 函數) ...
# ...
# --- 在檔案最底部加入這個區塊 ---

from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from db.db import get_db
from db import models as db_models

# 這是一個 "依賴項" (Dependency)
# 它可以被注入到任何需要「已登入」狀態的 API 路由中
def get_current_user(
    request: Request, 
    db: Session = Depends(get_db)
) -> db_models.User: # 它會回傳一個 SQLAlchemy 的 User 物件
    
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db_user = db.query(db_models.User).filter(db_models.User.id == user_id).first()
    if not db_user:
        request.session.clear() # 防禦性程式碼
        raise HTTPException(status_code=401, detail="User not found, session cleared")
    
    return db_user

# --- 這兩個是專門用來檢查「角色」的依賴項 ---

def get_current_client(
    current_user: db_models.User = Depends(get_current_user)
) -> db_models.User:
    if current_user.role != 'client':
        raise HTTPException(status_code=403, detail="Operation not permitted: Requires client role")
    return current_user

def get_current_contractor(
    current_user: db_models.User = Depends(get_current_user)
) -> db_models.User:
    if current_user.role != 'contractor':
        raise HTTPException(status_code=403, detail="Operation not permitted: Requires contractor role")
    return current_user