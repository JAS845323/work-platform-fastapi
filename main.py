# main.py

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from starlette.middleware.sessions import SessionMiddleware
import os # <-- 修正 1: 匯入 OS 模組

# 匯入我們的路由
from routes import auth, projects, upload
# 匯入DB和模型
from db.db import get_db
from db import models as db_models

app = FastAPI()

# -----------------------------------------------
# 1. 載入 Middleware (中間層)
# -----------------------------------------------
app.add_middleware(
    SessionMiddleware,
    secret_key="aBcDeF!@#$zYxWvU%^&*9876",
    max_age=86400,
)

# -----------------------------------------------
# 2. 載入靜態檔案 (CSS, JS, 圖片)
# -----------------------------------------------

# *** 這是修正後的邏輯 ***
# 修正 2: 在掛載前，先定義並建立資料夾
UPLOAD_DIRECTORY = "uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

app.mount("/static", StaticFiles(directory="static"), name="static")
# 修正 3: 現在这个掛載會 100% 成功
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

# --- 依賴項：檢查 Session 並取得使用者 ---
def get_user_from_session(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/", status_code=303)
        
    user = db.query(db_models.User).filter(db_models.User.id == user_id).first()
    if not user:
        request.session.clear()
        return RedirectResponse(url="/", status_code=303)
    
    return user

# --- 頁面：登入頁 ---
@app.get("/", response_class=HTMLResponse)
def get_login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
        
    return templates.TemplateResponse("login.html", {"request": request})

# --- 頁面：註冊頁 ---
@app.get("/register", response_class=HTMLResponse)
def get_register_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
        
    return templates.TemplateResponse("register.html", {"request": request})

# --- 頁面：首頁 (原儀表板) (受保護) ---
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard(
    request: Request, 
    user: db_models.User = Depends(get_user_from_session),
    db: Session = Depends(get_db)
):
    context = {"request": request, "user": user}
    
    if user.role == 'client':
        my_projects = db.query(db_models.Project).filter(
            db_models.Project.client_id == user.id
        ).order_by(db_models.Project.created_at.desc()).all()
        context["my_projects"] = my_projects
    else:
        my_projects = db.query(db_models.Project).filter(
            db_models.Project.selected_contractor_id == user.id
        ).order_by(db_models.Project.created_at.desc()).all()
        context["my_projects"] = my_projects
        
        open_projects = db.query(db_models.Project).filter(
            db_models.Project.status == 'open'
        ).order_by(db_models.Project.created_at.desc()).all()
        context["open_projects"] = open_projects

    return templates.TemplateResponse("dashboard.html", context)

# --- 頁面：建立新專案 ---
@app.get("/project/create", response_class=HTMLResponse)
def get_create_project_page(
    request: Request,
    user: db_models.User = Depends(get_user_from_session)
):
    if user.role != 'client':
        return RedirectResponse(url="/dashboard", status_code=403)
        
    return templates.TemplateResponse("project_create.html", {"request": request, "user": user})

# --- 頁面：專案詳情頁 ---
@app.get("/project/{project_id}", response_class=HTMLResponse)
def get_project_detail_page(
    project_id: int,
    request: Request,
    user: db_models.User = Depends(get_user_from_session),
    db: Session = Depends(get_db)
):
    db_project = db.query(db_models.Project).options(
        joinedload(db_models.Project.bids).joinedload(db_models.Bid.contractor),
        joinedload(db_models.Project.communications).joinedload(db_models.Communication.sender),
        joinedload(db_models.Project.deliverables), # 載入交付成果
        joinedload(db_models.Project.client)
    ).filter(db_models.Project.id == project_id).first()

    if not db_project:
        return RedirectResponse(url="/dashboard", status_code=404)

    is_owner = (db_project.client.id == user.id) 
    is_selected_contractor = (db_project.selected_contractor_id == user.id)
    is_contractor = (user.role == 'contractor')

    if db_project.status == 'open' and is_contractor:
        pass
    elif db_project.status != 'open' and not (is_owner or is_selected_contractor):
         return RedirectResponse(url="/dashboard", status_code=403)

    messages = sorted(db_project.communications, key=lambda m: m.created_at)
    bids = sorted(db_project.bids, key=lambda b: b.created_at)
    # 傳遞交付成果到前端
    deliverables = sorted(db_project.deliverables, key=lambda d: d.uploaded_at, reverse=True)


    return templates.TemplateResponse("project_detail.html", {
        "request": request,
        "user": user,
        "project": db_project,
        "bids": bids,
        "messages": messages,
        "deliverables": deliverables # <-- 傳遞檔案列表
    })

# --- 頁面：登出 ---
@app.get("/page/logout")
def page_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)