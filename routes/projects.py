# routes/projects.py

import os
import shutil
import uuid
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

# 匯入資料庫與模型
from db.db import get_db
from db import models as db_models
from models import project as pydantic_models
from models import communication as pydantic_comm_models
from models import bid as pydantic_bid_models
from auth.security import get_current_client, get_current_contractor, get_current_user
from websocket_manager import manager

router = APIRouter()


# --- API 1: 建立專案 ---
@router.post("/", response_model=pydantic_models.Project)
def create_project(
    title: str = Form(...),
    description: str | None = Form(None),
    deadline: str | None = Form(None),
    budget: str | None = Form(None),
    db: Session = Depends(get_db),
    current_client: db_models.User = Depends(get_current_client) 
):
    try:
        # 手動觸發 Pydantic 驗證，這樣可以利用 models/project.py 裡寫好的清洗邏輯
        # (它會自動處理空字串、移除逗號、轉換日期格式)
        project = pydantic_models.ProjectCreate(
            title=title, description=description, deadline=deadline, budget=budget
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    db_project = db_models.Project(
        title=project.title,
        description=project.description,
        client_id=current_client.id,
        deadline=project.deadline,
        budget=project.budget
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

# --- API 2: 查詢開放專案 ---
@router.get("/open", response_model=List[pydantic_models.Project])
def get_open_projects(
    db: Session = Depends(get_db),
    current_contractor: db_models.User = Depends(get_current_contractor)
):
    projects = db.query(db_models.Project).options(
        joinedload(db_models.Project.client)
    ).filter(db_models.Project.status == 'open').all()
    return projects

# --- API 3: 提出報價 (支援 PDF 上傳與限時檢查) ---
@router.post("/{project_id}/bid", response_model=pydantic_bid_models.Bid)
def create_bid_for_project(
    project_id: int,
    bid_amount: float = Form(...),
    proposal_text: str | None = Form(None),
    file: UploadFile = File(...), # [延伸一] 必傳 PDF
    db: Session = Depends(get_db),
    current_contractor: db_models.User = Depends(get_current_contractor)
):
    # 1. 檢查專案
    db_project = db.query(db_models.Project).filter(
        db_models.Project.id == project_id,
        db_models.Project.status == 'open'
    ).first()
    
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found or not open for bidding")

    # [延伸一] 限時檢查
    if db_project.deadline and datetime.now() > db_project.deadline:
        raise HTTPException(status_code=400, detail="Bidding deadline has passed (競標已截止)")

    # 2. 檢查重複投標
    existing_bid = db.query(db_models.Bid).filter(
        db_models.Bid.project_id == project_id,
        db_models.Bid.contractor_id == current_contractor.id
    ).first()
    if existing_bid:
        raise HTTPException(status_code=400, detail="You have already placed a bid on this project")

    # [延伸一] 3. 檢查 PDF
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed for proposals")

    # [延伸一] 4. 儲存檔案
    UPLOAD_DIRECTORY = "uploads"
    if not os.path.exists(UPLOAD_DIRECTORY):
        os.makedirs(UPLOAD_DIRECTORY)
        
    safe_filename = f"{uuid.uuid4()}.pdf"
    file_path = os.path.join(UPLOAD_DIRECTORY, safe_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    # 5. 寫入 DB
    db_bid = db_models.Bid(
        project_id=project_id,
        contractor_id=current_contractor.id,
        bid_amount=bid_amount,
        proposal_text=proposal_text,
        proposal_file_path=safe_filename
    )
    
    db.add(db_bid)
    db.commit()
    db.refresh(db_bid)
    return db_bid

# --- API 4: 查詢投標 ---
@router.get("/{project_id}/bids", response_model=List[pydantic_bid_models.Bid])
def get_bids_for_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_client: db_models.User = Depends(get_current_client)
):
    db_project = db.query(db_models.Project).options(
        joinedload(db_models.Project.bids).joinedload(db_models.Bid.contractor)
    ).filter(
        db_models.Project.id == project_id,
        db_models.Project.client_id == current_client.id
    ).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found or you do not own this project")
    return db_project.bids

# --- API 5: 選擇委託對象 ---
@router.post("/{project_id}/select_bid/{bid_id}", response_model=pydantic_models.Project)
def select_bid_for_project(
    project_id: int,
    bid_id: int,
    db: Session = Depends(get_db),
    current_client: db_models.User = Depends(get_current_client)
):
    db_project = db.query(db_models.Project).filter(
        db_models.Project.id == project_id,
        db_models.Project.client_id == current_client.id,
        db_models.Project.status == 'open'
    ).first()
    
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found, not owned by you, or already in progress")

    # [已修改] 原本這裡有一段檢查截止時間的程式碼，現在我們把它移除，讓您可以隨時決標！
    # if db_project.deadline and datetime.now() < db_project.deadline:
    #     raise HTTPException(status_code=400, detail="Cannot select bid before deadline (競標尚未截止，無法決標)")

    db_bid = db.query(db_models.Bid).filter(
        db_models.Bid.id == bid_id,
        db_models.Bid.project_id == project_id
    ).first()
    if not db_bid:
        raise HTTPException(status_code=404, detail="Bid not found for this project")

    db_project.status = 'in_progress'
    db_project.selected_contractor_id = db_bid.contractor_id
    db.commit()
    db.refresh(db_project)
    return db_project
# --- API 7: 歷史專案 ---
@router.get("/mine", response_model=List[pydantic_models.Project])
def get_my_projects(
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    if current_user.role == 'client':
        projects = db.query(db_models.Project).options(
            joinedload(db_models.Project.client),
            joinedload(db_models.Project.contractor)
        ).filter(
            db_models.Project.client_id == current_user.id
        ).all()
    else:
        projects = db.query(db_models.Project).options(
            joinedload(db_models.Project.client) 
        ).filter(
            db_models.Project.selected_contractor_id == current_user.id
        ).all()
    return projects

# --- API 8: 修改專案 ---
@router.put("/{project_id}", response_model=pydantic_models.Project)
def update_project(
    project_id: int,
    project_update: pydantic_models.ProjectUpdate,
    db: Session = Depends(get_db),
    current_client: db_models.User = Depends(get_current_client)
):
    db_project = db.query(db_models.Project).options(
        joinedload(db_models.Project.client)
    ).filter(
        db_models.Project.id == project_id,
        db_models.Project.client_id == current_client.id
    ).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found or not owned by you")

    if db_project.status != 'open':
        raise HTTPException(status_code=400, detail="Only 'open' projects can be updated")
        
    db_project.title = project_update.title
    db_project.description = project_update.description
    db.commit()
    db.refresh(db_project)
    return db_project

# --- API 9: 結案管理 (含 Issue 檢查) ---
@router.post("/{project_id}/status", response_model=pydantic_models.Project)
def update_project_status(
    project_id: int,
    status_update: pydantic_models.ProjectStatusUpdate,
    db: Session = Depends(get_db),
    current_client: db_models.User = Depends(get_current_client)
):
    new_status = status_update.status
    db_project = db.query(db_models.Project).filter(
        db_models.Project.id == project_id,
        db_models.Project.client_id == current_client.id
    ).first()
    
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found or not owned by you")

    current_status = db_project.status
    allowed_transitions = {
        'in_progress': ['completed', 'rejected'],
        'rejected': ['in_progress']
    }

    if current_status in allowed_transitions and new_status in allowed_transitions[current_status]:
        # [延伸三] 結案前檢查 Issue Tracker
        if new_status == 'completed':
            open_issues = db.query(db_models.Issue).filter(
                db_models.Issue.project_id == project_id,
                db_models.Issue.status == 'open'
            ).count()
            if open_issues > 0:
                raise HTTPException(status_code=400, detail=f"Cannot complete project with {open_issues} open issues.")
        
        db_project.status = new_status
        db.commit()
        db.refresh(db_project)
        return db_project
    else:
        raise HTTPException(status_code=400, detail=f"Invalid status transition from '{current_status}' to '{new_status}'")

# --- API 10: 傳送訊息 ---
@router.post("/{project_id}/messages", response_model=pydantic_comm_models.Message)
async def create_message_for_project(
    project_id: int,
    message: pydantic_comm_models.MessageCreate,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    # [資安防護] 輸入長度驗證：防止惡意長字串攻擊 (DoS)
    if len(message.message) > 1000:
        raise HTTPException(status_code=400, detail="Message is too long (limit: 1000 characters).")

    db_project = db.query(db_models.Project).filter(db_models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if (db_project.client_id != current_user.id and 
        db_project.selected_contractor_id != current_user.id):
        raise HTTPException(status_code=403, detail="You are not part of this project")

    db_message = db_models.Communication(
        project_id=project_id,
        sender_id=current_user.id,
        message=message.message
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    # [WebSocket] 廣播訊息
    await manager.broadcast(project_id, {
        "type": "chat_message",
        "sender_id": current_user.id,
        "payload": {
            "message": db_message.message,
            "sender_name": current_user.username,
            "created_at": db_message.created_at.isoformat() if db_message.created_at else datetime.now().isoformat()
        }
    })
    return db_message

# --- API 11: 讀取訊息 ---
@router.get("/{project_id}/messages", response_model=List[pydantic_comm_models.Message])
def get_messages_for_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    db_project = db.query(db_models.Project).options(
        joinedload(db_models.Project.communications).joinedload(db_models.Communication.sender)
    ).filter(db_models.Project.id == project_id).first()
    
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    if (db_project.client_id != current_user.id and 
        db_project.selected_contractor_id != current_user.id):
        raise HTTPException(status_code=403, detail="You are not part of this project")
        
    messages = sorted(db_project.communications, key=lambda m: m.created_at)
    return messages

# --- API 13: 刪除專案 ---
@router.delete("/{project_id}", status_code=200)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_client: db_models.User = Depends(get_current_client)
):
    db_project = db.query(db_models.Project).filter(
        db_models.Project.id == project_id,
        db_models.Project.client_id == current_client.id
    ).first()

    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found or not owned by you")

    if db_project.status != 'open':
        raise HTTPException(status_code=400, detail="Only 'open' projects can be deleted.")

    try:
        db.delete(db_project)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete project: {e}")

    return {"message": "Project deleted successfully"}

# --- API 14: 評價系統 [延伸二] ---
@router.post("/{project_id}/rate", response_model=pydantic_models.Rating)
def submit_rating(
    project_id: int,
    rating: pydantic_models.RatingCreate,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    # [資安防護] 1. 數值範圍驗證：防止惡意使用者繞過前端發送異常分數 (如 -100 或 9999)
    if not (1 <= rating.score_dim1 <= 5 and 1 <= rating.score_dim2 <= 5 and 1 <= rating.score_dim3 <= 5):
        raise HTTPException(status_code=400, detail="Invalid score: Ratings must be integers between 1 and 5.")

    # [資安防護] 2. 輸入長度驗證：防止惡意長字串攻擊 (DoS) 或資料庫欄位溢位
    if rating.comment and len(rating.comment) > 500:
        raise HTTPException(status_code=400, detail="Comment is too long (limit: 500 characters).")

    db_project = db.query(db_models.Project).filter(db_models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    if db_project.status != 'completed':
        raise HTTPException(status_code=400, detail="You can only rate completed projects")

    if current_user.id == db_project.client_id:
        to_user_id = db_project.selected_contractor_id
    elif current_user.id == db_project.selected_contractor_id:
        to_user_id = db_project.client_id
    else:
        raise HTTPException(status_code=403, detail="You are not part of this project")

    existing = db.query(db_models.Rating).filter(
        db_models.Rating.project_id == project_id, 
        db_models.Rating.from_user_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already rated this project")

    db_rating = db_models.Rating(
        project_id=project_id,
        from_user_id=current_user.id,
        to_user_id=to_user_id,
        score_dim1=rating.score_dim1,
        score_dim2=rating.score_dim2,
        score_dim3=rating.score_dim3,
        comment=rating.comment
    )
    db.add(db_rating)
    
    # [新增] 更新被評分者的平均分數與次數
    db.flush() # 讓新評分生效以便計算
    
    avg_score_expr = (db_models.Rating.score_dim1 + db_models.Rating.score_dim2 + db_models.Rating.score_dim3) / 3.0
    stats = db.query(
        func.count(db_models.Rating.id),
        func.avg(avg_score_expr)
    ).filter(db_models.Rating.to_user_id == to_user_id).first()
    
    to_user = db.query(db_models.User).filter(db_models.User.id == to_user_id).first()
    if to_user and stats:
        to_user.rating_count = stats[0]
        to_user.average_rating = float(stats[1]) if stats[1] is not None else 0.0

    db.commit()
    db.refresh(db_rating)
    return db_rating

# --- API 15: Issue Tracker - 新增 [延伸三] ---
@router.post("/{project_id}/issues", response_model=pydantic_models.Issue)
async def create_issue(
    project_id: int,
    issue: pydantic_models.IssueCreate,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    db_project = db.query(db_models.Project).filter(db_models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if db_project.status not in ['in_progress', 'rejected']:
        raise HTTPException(status_code=400, detail="Issues allowed only in progress/rejected status")
    
    # [修正點] 嚴格限制：只有甲方 (Client) 可以建立 Issue
    if current_user.id != db_project.client_id:
        raise HTTPException(status_code=403, detail="Only the client (owner) can create issues")

    db_issue = db_models.Issue(
        project_id=project_id,
        title=issue.title,
        created_by_id=current_user.id,
        status='open'
    )
    db.add(db_issue)
    db.commit()
    db.refresh(db_issue)
    
    # [WebSocket] 通知更新 Issue 列表
    await manager.broadcast(project_id, {
        "type": "issue_update",
        "sender_id": current_user.id,
        "payload": {"action": "created", "issue_id": db_issue.id}
    })
    return db_issue

# --- API 16: Issue Tracker - 列表/更新/留言 [延伸三] ---
@router.get("/{project_id}/issues", response_model=List[pydantic_models.Issue])
def get_issues(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    db_project = db.query(db_models.Project).filter(db_models.Project.id == project_id).first()
    if not db_project or current_user.id not in [db_project.client_id, db_project.selected_contractor_id]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # 使用 options(joinedload) 預載資料
    issues = db.query(db_models.Issue).options(
        joinedload(db_models.Issue.creator),
        joinedload(db_models.Issue.comments).joinedload(db_models.IssueComment.sender)
    ).filter(db_models.Issue.project_id == project_id).all()
    return issues

@router.post("/issues/{issue_id}/comments", response_model=pydantic_models.IssueComment)
async def create_issue_comment(
    issue_id: int,
    comment: pydantic_models.IssueCommentCreate,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    db_issue = db.query(db_models.Issue).filter(db_models.Issue.id == issue_id).first()
    if not db_issue:
        raise HTTPException(status_code=404, detail="Issue not found")
        
    project_id = db_issue.project_id

    db_comment = db_models.IssueComment(
        issue_id=issue_id,
        user_id=current_user.id,
        content=comment.content
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    # [WebSocket] 通知更新 Issue 內容
    await manager.broadcast(project_id, {
        "type": "issue_comment",
        "sender_id": current_user.id,
        "payload": {"issue_id": issue_id}
    })
    return db_comment

@router.put("/issues/{issue_id}/resolve")
async def resolve_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_client: db_models.User = Depends(get_current_client) # 只有甲方能解決
):
    db_issue = db.query(db_models.Issue).options(joinedload(db_models.Issue.project)).filter(db_models.Issue.id == issue_id).first()
    if not db_issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if db_issue.project.client_id != current_client.id:
        raise HTTPException(status_code=403, detail="Only client can resolve issues")
        
    db_issue.status = 'resolved'
    db.commit()
    
    # [WebSocket] 通知 Issue 狀態變更
    await manager.broadcast(db_issue.project_id, {
        "type": "issue_update",
        "sender_id": current_client.id,
        "payload": {"action": "resolved", "issue_id": issue_id}
    })
    return {"message": "Issue resolved"}
    
@router.post("/{project_id}/favorite")
def toggle_favorite(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # 從資料庫取得使用者與專案
    user = db.query(db_models.User).filter(db_models.User.id == user_id).first()
    project = db.query(db_models.Project).filter(db_models.Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # 檢查是否已收藏：有則移除，無則新增
    if project in user.favorite_projects:
        user.favorite_projects.remove(project)
        is_favorited = False
    else:
        user.favorite_projects.append(project)
        is_favorited = True
        
    db.commit()
    return {"is_favorited": is_favorited}
