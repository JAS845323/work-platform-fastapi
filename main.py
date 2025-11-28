# main.py

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, update
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import os

# 匯入我們的路由
from routes import auth, projects, upload

# 匯入DB和模型
# *** 修改點 1: 這裡多匯入了 engine ***
from db.db import get_db, engine
from db import models as db_models


# 1. 載入 .env 檔案中的變數
load_dotenv()

# =================================================
# *** 修改點 2: 加入這行來自動建立資料表 ***
# 這行程式碼會檢查資料庫，如果 models.py 定義的表不存在，就會自動建立！
# =================================================
db_models.Base.metadata.create_all(bind=engine)


app = FastAPI()

# -----------------------------------------------
# 1. 載入 Middleware (中間層)
# -----------------------------------------------
app.add_middleware(
    SessionMiddleware,
    # 2. 改從環境變數讀取 SECRET_KEY，若讀不到則使用後面的預設值
    secret_key=os.getenv("SECRET_KEY", "fallback_secret_key_if_env_missing"),
    max_age=86400,
)

# -----------------------------------------------
# 2. 載入靜態檔案 (CSS, JS, 圖片)
# -----------------------------------------------
UPLOAD_DIRECTORY = "uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory=UPLOAD_DIRECTORY), name="media")


# -----------------------------------------------
# 3. 載入樣板 (Jinja2)
# -----------------------------------------------
templates = Jinja2Templates(directory="templates")

# -----------------------------------------------
# 4. 載入 API Routers (後端)
# -----------------------------------------------
app.include_router(auth.router, prefix="/api/auth", tags=["API - Authentication"])
app.include_router(projects.router, prefix="/api/projects", tags=["API - Projects"])
app.include_router(upload.router, prefix="/api", tags=["API - Upload"])


# -----------------------------------------------
# 5. 載入 Page Routers (前端)
# -----------------------------------------------

# --- 
# 「守衛」依賴項
# 
def get_user_from_session(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        # 未登入，重導至首頁
        return RedirectResponse(url="/", status_code=303) 
        
    user = db.query(db_models.User).filter(db_models.User.id == user_id).first()
    if not user:
        request.session.clear()
        return RedirectResponse(url="/", status_code=303) # 找不到用戶，重導至首頁
    
    # 守衛已通過
    return True

# --- 頁面：登陸頁 (首頁) ---
@app.get("/", response_class=HTMLResponse)
def get_landing_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
        
    return templates.TemplateResponse("landing.html", {"request": request})

# --- 頁面：登入頁 ---
@app.get("/login", response_class=HTMLResponse)
def get_login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
        
    return templates.TemplateResponse("login.html", {"request": request, "unread_count": 0})

# --- 頁面：註冊頁 ---
@app.get("/register", response_class=HTMLResponse)
def get_register_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
        
    return templates.TemplateResponse("register.html", {"request": request, "unread_count": 0})

# --- 頁面：首頁 (Dashboard) ---
@app.get(
    "/dashboard", 
    response_class=HTMLResponse,
    dependencies=[Depends(get_user_from_session)] # 1. 先執行「守衛」
)
def get_dashboard(
    request: Request, # 2. 「守衛」通過後，才執行此函數
    db: Session = Depends(get_db)
):
    # 3. 我們現在 100% 確定 user_id 存在
    user_id = request.session.get("user_id")
    user = db.query(db_models.User).filter(db_models.User.id == user_id).first()
    
    if not user: # 安全檢查，以防萬一
        request.session.clear()
        return RedirectResponse(url="/", status_code=303)

    context = {"request": request, "user": user}
    
    my_project_ids_query = db.query(db_models.Project.id)
    if user.role == 'client':
        my_project_ids_query = my_project_ids_query.filter(db_models.Project.client_id == user.id)
    else:
        my_project_ids_query = my_project_ids_query.filter(db_models.Project.selected_contractor_id == user.id)
    
    my_project_ids = [id[0] for id in my_project_ids_query.all()]
    
    # 4. 查詢「未讀訊息」
    unread_count = 0
    recent_messages = []
    
    if my_project_ids:
        unread_count = db.query(db_models.Communication).filter(
            db_models.Communication.project_id.in_(my_project_ids),
            db_models.Communication.sender_id != user.id,
            db_models.Communication.is_read == False
        ).count()
        
        recent_messages = db.query(db_models.Communication).options(
            joinedload(db_models.Communication.sender),
            joinedload(db_models.Communication.project)
        ).filter(
            db_models.Communication.project_id.in_(my_project_ids),
            db_models.Communication.sender_id != user.id
        ).order_by(
            db_models.Communication.is_read.asc(),
            db_models.Communication.created_at.desc()
        ).limit(5).all()
        
    context["recent_messages"] = recent_messages
    context["unread_count"] = unread_count

    
    # 5. 抓取專案列表
    if user.role == 'client':
        my_projects = db.query(db_models.Project).options(
            joinedload(db_models.Project.client)
        ).filter(
            db_models.Project.client_id == user.id
        ).order_by(db_models.Project.created_at.desc()).all()
        context["my_projects"] = my_projects
    else:
        my_projects = db.query(db_models.Project).options(
            joinedload(db_models.Project.client)
        ).filter(
            db_models.Project.selected_contractor_id == user.id
        ).order_by(db_models.Project.created_at.desc()).all()
        context["my_projects"] = my_projects
        
        open_projects = db.query(db_models.Project).options(
            joinedload(db_models.Project.client)
        ).filter(
            db_models.Project.status == 'open'
        ).order_by(db_models.Project.created_at.desc()).all()
        context["open_projects"] = open_projects

        # 6. 數據統計
        stats = db.query(
            func.count(case((
                (db_models.Project.selected_contractor_id == user.id) & (db_models.Project.status == 'in_progress'), 1
            ))).label('in_progress'),
            func.count(case((
                (db_models.Project.selected_contractor_id == user.id) & (db_models.Project.status == 'completed'), 1
            ))).label('completed'),
            func.count(case((db_models.Project.status == 'open', 1))).label('open')
        ).first()
        
        context["stats"] = {
            "in_progress": stats.in_progress,
            "completed": stats.completed,
            "open": stats.open
        }

    return templates.TemplateResponse("dashboard.html", context)

# --- 頁面：建立新專案 ---
@app.get(
    "/project/create", 
    response_class=HTMLResponse,
    dependencies=[Depends(get_user_from_session)]
)
def get_create_project_page(
    request: Request,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    user = db.query(db_models.User).filter(db_models.User.id == user_id).first()

    if user.role != 'client':
        return RedirectResponse(url="/dashboard", status_code=403)
        
    # 傳遞 unread_count
    unread_count = db.query(db_models.Communication).join(db_models.Project).filter(
        db_models.Project.client_id == user_id,
        db_models.Communication.sender_id != user_id,
        db_models.Communication.is_read == False
    ).count()

    return templates.TemplateResponse("project_create.html", {"request": request, "user": user, "unread_count": unread_count})

# --- 頁面：專案詳情頁 ---
@app.get(
    "/project/{project_id}", 
    response_class=HTMLResponse,
    dependencies=[Depends(get_user_from_session)]
)
def get_project_detail_page(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    user = db.query(db_models.User).filter(db_models.User.id == user_id).first()

    # 1. 抓取專案
    db_project = db.query(db_models.Project).options(
        joinedload(db_models.Project.bids).joinedload(db_models.Bid.contractor),
        joinedload(db_models.Project.communications).joinedload(db_models.Communication.sender),
        joinedload(db_models.Project.deliverables),
        joinedload(db_models.Project.client)
    ).filter(db_models.Project.id == project_id).first()

    if not db_project:
        return RedirectResponse(url="/dashboard", status_code=404)

    # 2. 權限檢查
    is_owner = (db_project.client.id == user.id) 
    is_selected_contractor = (db_project.selected_contractor_id == user.id)
    is_contractor = (user.role == 'contractor')

    if db_project.status == 'open' and is_contractor:
        pass
    elif db_project.status != 'open' and not (is_owner or is_selected_contractor):
         return RedirectResponse(url="/dashboard", status_code=303)

    # 3. 標記訊息為已讀
    try:
        stmt = update(db_models.Communication).where(
            db_models.Communication.project_id == project_id,
            db_models.Communication.sender_id != user_id,
            db_models.Communication.is_read == False
        ).values(
            is_read = True
        )
        db.execute(stmt)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error marking messages as read: {e}")
    
    # 4. 抓取並排序關聯資料
    messages = sorted(db_project.communications, key=lambda m: m.created_at)
    bids = sorted(db_project.bids, key=lambda b: b.created_at)
    deliverables = sorted(db_project.deliverables, key=lambda d: d.uploaded_at, reverse=True)

    # 5. 傳遞 unread_count
    my_project_ids = [p.id for p in user.projects_created] if user.role == 'client' else [p.id for p in user.projects_assigned]
    unread_count = 0
    if my_project_ids:
        unread_count = db.query(db_models.Communication).filter(
            db_models.Communication.project_id.in_(my_project_ids),
            db_models.Communication.sender_id != user_id,
            db_models.Communication.is_read == False
        ).count()

    return templates.TemplateResponse("project_detail.html", {
        "request": request,
        "user": user,
        "project": db_project,
        "bids": bids,
        "messages": messages,
        "deliverables": deliverables,
        "unread_count": unread_count
    })

# --- 頁面：編輯專案頁 ---
@app.get(
    "/project/edit/{project_id}", 
    response_class=HTMLResponse,
    dependencies=[Depends(get_user_from_session)]
)
def get_edit_project_page(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    user = db.query(db_models.User).filter(db_models.User.id == user_id).first()

    db_project = db.query(db_models.Project).filter(
        db_models.Project.id == project_id
    ).first()

    if not db_project or db_project.client_id != user.id:
        return RedirectResponse(url="/dashboard", status_code=403)
    
    if db_project.status != 'open':
        return RedirectResponse(url=f"/project/{project_id}", status_code=400)

    # 傳遞 unread_count
    my_project_ids = [p.id for p in user.projects_created]
    unread_count = 0
    if my_project_ids:
        unread_count = db.query(db_models.Communication).filter(
            db_models.Communication.project_id.in_(my_project_ids),
            db_models.Communication.sender_id != user_id,
            db_models.Communication.is_read == False
        ).count()

    return templates.TemplateResponse("project_edit.html", {
        "request": request,
        "user": user,
        "project": db_project,
        "unread_count": unread_count
    })

# --- 頁面：登出 ---
@app.get("/page/logout")
def page_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)