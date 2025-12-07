from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. 資料庫連線 URL
# 格式: "postgresql://使用者名稱:密碼@主機:Port/資料庫名稱"
# 根據你的簡報 和 Adminer 截圖，你應該是連到本地 (localhost)
# 預設管理員是 'postgres'，密碼是你安裝時設定的
DATABASE_URL = "postgresql://postgres:0306@localhost:5432/postgres"

# 2. 建立 SQLAlchemy 引擎
engine = create_engine(DATABASE_URL)

# 3. 建立 SessionLocal
# 這將是我們與資料庫溝通的 "會話" (session)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 建立 Base
# 我們的資料庫模型 (db/models.py) 將會繼承這個 Base
Base = declarative_base()

# -------------------------------------------------
# 依賴注入 (Dependency Injection)
# 這是你簡報 中提到的 "Depends" 的關鍵應用
# -------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()