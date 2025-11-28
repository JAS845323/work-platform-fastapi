# routes/upload.py

import os
import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func 

# 匯入我們建立的東西
from db.db import get_db
from db import models as db_models
from auth.security import get_current_contractor

# 建立一個新的 APIRouter
router = APIRouter()

UPLOAD_DIRECTORY = "uploads" 

# --- API 6: 上傳結案檔案 (含版本控管 [延伸一] + 自動狀態切換) ---
@router.post("/projects/{project_id}/upload", status_code=201)
def upload_deliverable(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_contractor: db_models.User = Depends(get_current_contractor)
):
    # 1. 檢查專案
    # [關鍵修正] 移除 .filter(status='in_progress')，否則退件狀態會找不到專案
    db_project = db.query(db_models.Project).filter(
        db_models.Project.id == project_id,
        db_models.Project.selected_contractor_id == current_contractor.id
    ).first()

    # 2. 在這裡才檢查狀態 (允許 in_progress 或 rejected)
    if not db_project or db_project.status not in ['in_progress', 'rejected']:
        raise HTTPException(status_code=404, detail="Project not found, not assigned to you, or not in active state")

    # [延伸一] 版本控管：計算新版本號
    max_version = db.query(func.max(db_models.Deliverable.version)).filter(
        db_models.Deliverable.project_id == project_id,
        db_models.Deliverable.contractor_id == current_contractor.id
    ).scalar() or 0
    
    new_version = max_version + 1

    # 3. 處理檔案儲存
    file_extension = os.path.splitext(file.filename)[1]
    safe_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIRECTORY, safe_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    # 4. 將檔案路徑寫入資料庫
    db_deliverable = db_models.Deliverable(
        project_id=project_id,
        contractor_id=current_contractor.id,
        file_path=safe_filename, # 只儲存檔名
        version=new_version      # [延伸一] 寫入版本號
    )
    db.add(db_deliverable)
    
    # [關鍵修正] 如果專案是被退件狀態 (rejected)，上傳後自動改回 'in_progress'
    if db_project.status == 'rejected':
        db_project.status = 'in_progress'
        
    db.commit()
    db.refresh(db_deliverable)

    return {
        "filename": file.filename, 
        "stored_filename": safe_filename, 
        "id": db_deliverable.id,
        "version": new_version
    }


# --- API 12: 刪除結案檔案 (接案人功能) ---
@router.delete("/deliverable/{deliverable_id}", status_code=200)
def delete_deliverable(
    deliverable_id: int,
    db: Session = Depends(get_db),
    current_contractor: db_models.User = Depends(get_current_contractor)
):
    # 1. 查詢檔案，並同時載入專案資訊
    db_deliverable = db.query(db_models.Deliverable).options(
        joinedload(db_models.Deliverable.project)
    ).filter(
        db_models.Deliverable.id == deliverable_id
    ).first()

    # 2. 權限檢查
    if not db_deliverable:
        raise HTTPException(status_code=404, detail="File not found")
    
    # 檢查是否為檔案的上傳者
    if db_deliverable.contractor_id != current_contractor.id:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this file")
        
    # [修正] 允許在 'rejected' 狀態刪除檔案 (方便乙方修正)
    if db_deliverable.project.status not in ['in_progress', 'rejected']:
        raise HTTPException(status_code=400, detail="Cannot delete files from a completed project")

    # 3. 從硬碟刪除檔案
    file_path = os.path.join(UPLOAD_DIRECTORY, db_deliverable.file_path)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError as e:
        print(f"Error deleting file {file_path}: {e}")
        # raise HTTPException(status_code=500, detail="Could not delete file from server")

    # 4. 從資料庫刪除紀錄
    try:
        db.delete(db_deliverable)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete file record from database: {e}")

    return {"message": "File deleted successfully"}