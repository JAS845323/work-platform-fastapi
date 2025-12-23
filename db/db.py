import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base # 新版 SQLAlchemy 建議用法
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv # 記得 pip install python-dotenv

# 1. 載入 .env 環境變數
load_dotenv()

# 2. 讀取資料庫連線 URL
# 如果找不到環境變數，這裡會報錯提醒，避免連到錯誤的地方
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("錯誤：未設定 DATABASE_URL，請檢查 .env 檔案")

# 3. 建立 SQLAlchemy 引擎
engine = create_engine(DATABASE_URL)

# 4. 建立 SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 5. 建立 Base
Base = declarative_base()

# -------------------------------------------------
# 依賴注入 (Dependency Injection)
# -------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()