# main.py

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
# [已修正] 移除重複的 import joinedload
from sqlalchemy import func, case, update
from starlette.middleware.sessions import SessionMiddleware
from fastapi.exceptions import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler
from dotenv import load_dotenv
import os

# 匯入路由與DB
from routes import auth, projects, upload
from db.db import get_db, engine
from db import models as db_models

# 1. 載入環境變數與初始化資料表
load_dotenv()
db_models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# -----------------------------------------------
# 1. 異常處理器 (商用級 404 頁面)
# -----------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    if exc.status_code == 401:
        return RedirectResponse(url="/", status_code=303)
    return await http_exception_handler(request, exc)

# -----------------------------------------------
# 2. 中間層 (Middleware) 與 靜態檔案
# -----------------------------------------------
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "fallback_secret_key_if_env_missing"),
    max_age=86400,
)

UPLOAD_DIRECTORY = "uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory=UPLOAD_DIRECTORY), name="media")

templates = Jinja2Templates(directory="templates")

# -----------------------------------------------
# 3. 載入 API 路由
# -----------------------------------------------
app.include_router(auth.router, prefix="/api/auth", tags=["API - Authentication"])
app.include_router(projects.router, prefix="/api/projects", tags=["API - Projects"])
app.include_router(upload.router, prefix="/api", tags=["API - Upload"])

# -----------------------------------------------
# 4. 頁面路由 (Page Routers)
# -----------------------------------------------

# 「守衛」依賴項：確保使用者已登入
def get_user_from_session(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401)
    user = db.query(db_models.User).filter(db_models.User.id == user_id).first()
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401)
    return True

@app.get("/", response_class=HTMLResponse)
def get_landing_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
def get_login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
def get_register_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request})

# --- 首頁 (Dashboard)：整合搜尋與收藏 ---
@app.get("/dashboard", response_class=HTMLResponse, dependencies=[Depends(get_user_from_session)])
def get_dashboard(request: Request, db: Session = Depends(get_db), q: str = None):
    user_id = request.session.get("user_id")
    user = db.query(db_models.User).options(joinedload(db_models.User.favorite_projects)).filter(db_models.User.id == user_id).first()
    
    context = {"request": request, "user": user, "q": q}
    
    # 統計數據預設值
    stats_data = {"in_progress": 0, "completed": 0, "open": 0}

    # 1. 抓取未讀訊息與相關專案
    my_project_ids_query = db.query(db_models.Project.id)
    if user.role == 'client':
        my_project_ids_query = my_project_ids_query.filter(db_models.Project.client_id == user.id)
    else:
        my_project_ids_query = my_project_ids_query.filter(db_models.Project.selected_contractor_id == user.id)
    
    my_project_ids = [id[0] for id in my_project_ids_query.all()]
    
    # 計算全域未讀數量
    if my_project_ids:
        unread_count = db.query(db_models.Communication).filter(db_models.Communication.project_id.in_(my_project_ids), db_models.Communication.sender_id != user.id, db_models.Communication.is_read == False).count()
        recent_messages = db.query(db_models.Communication).options(joinedload(db_models.Communication.sender), joinedload(db_models.Communication.project)).filter(db_models.Communication.project_id.in_(my_project_ids), db_models.Communication.sender_id != user.id).order_by(db_models.Communication.created_at.desc()).limit(5).all()
        context.update({"unread_count": unread_count, "recent_messages": recent_messages})

    # 2. 專案清單邏輯
    if user.role == 'client':
        query = db.query(db_models.Project).filter(db_models.Project.client_id == user.id)
        if q: query = query.filter(db_models.Project.title.contains(q))
        context["my_projects"] = query.order_by(db_models.Project.created_at.desc()).all()
        
        # 甲方統計
        s = db.query(func.count(case((db_models.Project.status == 'in_progress', 1))).label('ip'), func.count(case((db_models.Project.status == 'completed', 1))).label('cp'), func.count(case((db_models.Project.status == 'open', 1))).label('op')).filter(db_models.Project.client_id == user.id).first()
        if s: stats_data = {"in_progress": s.ip, "completed": s.cp, "open": s.op}
    else:
        context["my_projects"] = db.query(db_models.Project).filter(db_models.Project.selected_contractor_id == user.id).all()
        open_query = db.query(db_models.Project).filter(db_models.Project.status == 'open')
        if q: open_query = open_query.filter(db_models.Project.title.contains(q))
        context["open_projects"] = open_query.all()

        # 乙方統計
        s = db.query(func.count(case(((db_models.Project.selected_contractor_id == user.id) & (db_models.Project.status == 'in_progress'), 1))).label('ip'), func.count(case(((db_models.Project.selected_contractor_id == user.id) & (db_models.Project.status == 'completed'), 1))).label('cp'), func.count(case((db_models.Project.status == 'open', 1))).label('op')).first()
        if s: stats_data = {"in_progress": s.ip, "completed": s.cp, "open": s.op}

    context["stats"] = stats_data
    return templates.TemplateResponse("dashboard.html", context)

# --- 專案詳情頁 ---
@app.get("/project/{project_id}", response_class=HTMLResponse, dependencies=[Depends(get_user_from_session)])
def get_project_detail_page(project_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    user = db.query(db_models.User).filter(db_models.User.id == user_id).first()

    db_project = db.query(db_models.Project).options(
        joinedload(db_models.Project.bids).joinedload(db_models.Bid.contractor),
        joinedload(db_models.Project.communications).joinedload(db_models.Communication.sender),
        joinedload(db_models.Project.ratings).joinedload(db_models.Rating.from_user),
        joinedload(db_models.Project.ratings).joinedload(db_models.Rating.to_user),
        joinedload(db_models.Project.deliverables),
        joinedload(db_models.Project.client),
        joinedload(db_models.Project.contractor)
    ).filter(db_models.Project.id == project_id).first()

    if not db_project: raise HTTPException(status_code=404)

    # 標記訊息為已讀
    db.query(db_models.Communication).filter(db_models.Communication.project_id == project_id, db_models.Communication.sender_id != user_id).update({"is_read": True})
    db.commit()

    # 定義對方資訊
    other_party = db_project.contractor if user.role == 'client' else db_project.client
    my_rating = next((r for r in db_project.ratings if r.from_user_id == user.id), None)
    
    # [已修正] 明確定義 unread_count_value 為 0
    # 因為使用者剛打開頁面，訊息已標記為已讀，所以針對此專案的未讀數為 0
    # 如果希望這裡顯示全域未讀數，需要額外查詢，但目前先設為 0 確保不報錯且符合邏輯
    unread_count_value = 0
    
    return templates.TemplateResponse("project_detail.html", {
        "request": request, "user": user, "project": db_project,
        "messages": sorted(db_project.communications, key=lambda m: m.created_at),
        "bids": db_project.bids, "deliverables": db_project.deliverables,
        "my_rating": my_rating, "other_party": other_party,
        "unread_count": unread_count_value, # 這裡現在有值了
    })

# --- 個人檔案頁：加入收藏與雷達圖數據 ---
@app.get("/user/{user_id_profile}", response_class=HTMLResponse, dependencies=[Depends(get_user_from_session)])
def get_user_profile_page(user_id_profile: int, request: Request, db: Session = Depends(get_db)):
    current_user_id = request.session.get("user_id")
    current_user = db.query(db_models.User).filter(db_models.User.id == current_user_id).first()

    # [已修正] 強制加載 (Eager Loading) 評價資料
    # 使用 joinedload 確保 ratings_received 被載入，這樣前端的雷達圖才有資料
    profile_user = db.query(db_models.User).options(
        joinedload(db_models.User.ratings_received).joinedload(db_models.Rating.from_user),
        joinedload(db_models.User.ratings_received).joinedload(db_models.Rating.project),
        joinedload(db_models.User.favorite_projects)
    ).filter(db_models.User.id == user_id_profile).first()

    if not profile_user: return RedirectResponse(url="/dashboard", status_code=404)

    return templates.TemplateResponse("user_profile.html", {
        "request": request, "user": current_user, "profile_user": profile_user,
        "is_own_profile": (current_user.id == profile_user.id)
    })

# --- 其他靜態與功能路由 ---
@app.get("/faq", response_class=HTMLResponse)
def get_faq_page(request: Request):
    return templates.TemplateResponse("info_page.html", {"request": request, "title": "常見問題 (FAQ)", "content": "<h3>Q1: TaskFlow 是什麼？</h3><p>TaskFlow 是一個專業的委託接案平台...</p>"})

@app.get("/privacy", response_class=HTMLResponse)
def get_privacy_page(request: Request):
    return templates.TemplateResponse("info_page.html", {"request": request, "title": "隱私政策", "content": "<p>我們重視您的隱私保護...</p>"})

@app.get("/terms", response_class=HTMLResponse)
def get_terms_page(request: Request):
    return templates.TemplateResponse("info_page.html", {"request": request, "title": "服務條款", "content": "<p>使用本服務即表示您同意以下條款...</p>"})

@app.get("/page/logout")
def page_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)