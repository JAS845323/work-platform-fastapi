# --- 1. 在檔案頂部，加入這些 imports ---
from fastapi import Request # <--- 加入這個
from auth.security import verify_password # <--- 加入這個

# ... (你原有的 router = APIRouter() 和 create_user 函數) ...
# ... (保留 @router.post("/register") ... )

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError # 用來捕捉重複的 username/email

# 匯入我們建立的東西
from db.db import get_db
from db import models as db_models # SQLAlchemy 模型
from models import user as pydantic_models # Pydantic 模型
from auth.security import get_password_hash

# 依照你的簡報 [cite: 6]，建立一個 APIRouter
router = APIRouter()

@router.post("/register", response_model=pydantic_models.User)
def create_user(
    user: pydantic_models.UserCreate, # 接收 Pydantic 模型
    db: Session = Depends(get_db)    # 注入資料庫連線
):
    # 1. 將 Pydantic 模型的密碼轉換為雜湊後的密碼
    hashed_password = get_password_hash(user.password)

    # 2. 建立 SQLAlchemy 模型 (準備寫入資料庫)
    db_user = db_models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        role=user.role
    )

    # 3. 寫入資料庫
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user) # 取得剛建立的 user (包含 ID)
        return db_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Username or email already registered."
        )
    # --- 2. 在檔案最底部 (create_user 函數之後)，加入以下三個新的 API 路由 ---

@router.post("/login")
def login(
    request: Request, # 為了操作 session
    user_login: pydantic_models.UserLogin, # 使用我們剛才建立的 Pydantic 模型
    db: Session = Depends(get_db)
):
    # 1. 檢查使用者是否存在
    db_user = db.query(db_models.User).filter(db_models.User.username == user_login.username).first()
    
    # (安全提示：為了防止時序攻擊，不論用戶是否存在，都執行密碼驗證)
    if not db_user or not verify_password(user_login.password, db_user.hashed_password):
        raise HTTPException(
            status_code=401, 
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}, # 雖然我們用 session，但 401 帶這個 header 是好習慣
        )

    # 3. 寫入 Session (登入成功)
    # 這是你簡報  提到的 session 應用
    request.session["user_id"] = db_user.id
    request.session["username"] = db_user.username
    request.session["role"] = db_user.role

    return {"username": db_user.username, "message": "Login successful"}

@router.get("/logout")
def logout(request: Request):
    # 4. 清除 Session (登出)
    request.session.clear()
    return {"message": "Logout successful"}

@router.get("/me", response_model=pydantic_models.User)
def read_users_me(request: Request, db: Session = Depends(get_db)):
    # 5. 驗證 Session (檢查登入狀態)
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db_user = db.query(db_models.User).filter(db_models.User.id == user_id).first()
    if not db_user:
        # 這種情況很少見，除非用戶在登入期間被刪除
        request.session.clear() 
        raise HTTPException(status_code=401, detail="User not found, session cleared")
    
    return db_user