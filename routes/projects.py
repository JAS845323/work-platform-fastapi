# routes/projects.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload # 確保 joinedload 已匯入
from typing import List

# 匯入我們建立的東西
from db.db import get_db
from db import models as db_models
from models import project as pydantic_models
from models import communication as pydantic_comm_models
from models import bid as pydantic_bid_models
from auth.security import get_current_client, get_current_contractor, get_current_user 

router = APIRouter()

# --- API 1: 建立專案 ---
@router.post("/", response_model=pydantic_models.Project)
def create_project(
    project: pydantic_models.ProjectCreate,
    db: Session = Depends(get_db),
    current_client: db_models.User = Depends(get_current_client) 
):
    db_project = db_models.Project(
        title=project.title,
        description=project.description,
        client_id=current_client.id
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

# --- API 3: 提出報價 ---
@router.post("/{project_id}/bid", response_model=pydantic_bid_models.Bid)
def create_bid_for_project(
    project_id: int,
    bid: pydantic_bid_models.BidCreate,
    db: Session = Depends(get_db),
    current_contractor: db_models.User = Depends(get_current_contractor)
):
    db_project = db.query(db_models.Project).filter(
        db_models.Project.id == project_id,
        db_models.Project.status == 'open'
    ).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found or not open for bidding")

    existing_bid = db.query(db_models.Bid).filter(
        db_models.Bid.project_id == project_id,
        db_models.Bid.contractor_id == current_contractor.id
    ).first()
    if existing_bid:
        raise HTTPException(status_code=400, detail="You have already placed a bid on this project")

    db_bid = db_models.Bid(
        project_id=project_id,
        contractor_id=current_contractor.id,
        bid_amount=bid.bid_amount,
        proposal_text=bid.proposal_text
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
        joinedload(db_models.Project.bids)
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

# --- API 7: 歷史專案列表 ---
@router.get("/mine", response_model=List[pydantic_models.Project])
def get_my_projects(
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    if current_user.role == 'client':
        projects = db.query(db_models.Project).options(
            joinedload(db_models.Project.client) # 預載 client
        ).filter(
            db_models.Project.client_id == current_user.id
        ).all()
    else:
        projects = db.query(db_models.Project).options(
            joinedload(db_models.Project.client) # 預載 client
        ).filter(
            db_models.Project.selected_contractor_id == current_user.id
        ).all()
    return projects

# --- API 8: 修改專案需求 ---
@router.put("/{project_id}", response_model=pydantic_models.Project)
def update_project(
    project_id: int,
    project_update: pydantic_models.ProjectUpdate,
    db: Session = Depends(get_db),
    current_client: db_models.User = Depends(get_current_client)
):
    db_project = db.query(db_models.Project).options(
        joinedload(db_models.Project.client) # 預載 client
    ).filter(
        db_models.Project.id == project_id,
        db_models.Project.client_id == current_client.id
    ).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found or not owned by you")

    if db_project.status != 'open':
        raise HTTPException(status_code=400, detail="Only projects with 'open' status can be updated")
        
    db_project.title = project_update.title
    db_project.description = project_update.description
    db.commit()
    db.refresh(db_project)
    return db_project

# --- API 9: 結案管理 ---
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
        db_project.status = new_status
        db.commit()
        db.refresh(db_project)
        return db_project
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status transition from '{current_status}' to '{new_status}'"
        )

# --- API 10: 傳送訊息 ---
@router.post("/{project_id}/messages", response_model=pydantic_comm_models.Message)
def create_message_for_project(
    project_id: int,
    message: pydantic_comm_models.MessageCreate,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):
    db_project = db.query(db_models.Project).filter(
        db_models.Project.id == project_id
    ).first()
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

# --- API 13: 取消(刪除)專案 (*** 新功能 ***) ---
@router.delete("/{project_id}", status_code=200)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_client: db_models.User = Depends(get_current_client)
):
    # 1. 驗證專案
    db_project = db.query(db_models.Project).filter(
        db_models.Project.id == project_id,
        db_models.Project.client_id == current_client.id
    ).first()

    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found or not owned by you")

    # 2. 只有 'open' 狀態的專案才能被刪除
    if db_project.status != 'open':
        raise HTTPException(status_code=400, detail="Only 'open' projects can be deleted. This project is already in progress.")

    # 3. 刪除 (由於我們設定了 CASCADE ondelete，相關的 bids, communications 等會自動刪除)
    try:
        db.delete(db_project)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete project: {e}")

    return {"message": "Project deleted successfully"}