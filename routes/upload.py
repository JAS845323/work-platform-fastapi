# routes/upload.py

import os
import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload # 匯入 joinedload

# 匯入我們建立的東西
from db.db import get_db
from db import models as db_models
from auth.security import get_current_contractor

# 建立一個新的 APIRouter
router = APIRouter()

UPLOAD_DIRECTORY = "uploads" 

# --- API 6: 上傳結案檔案 (接案人功能) ---
@router.post("/projects/{project_id}/upload", status_code=201)
def upload_deliverable(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_contractor: db_models.User = Depends(get_current_contractor)
):
    # 1. 檢查專案
    db_project = db.query(db_models.Project).filter(
        db_models.Project.id == project_id,
        db_models.Project.selected_contractor_id == current_contractor.id,
        db_models.Project.status == 'in_progress'
    ).first()

    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found, not assigned to you, or not in progress")

    # 2. 處理檔案儲存
    file_extension = os.path.splitext(file.filename)[1]
    safe_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIRECTORY, safe_filename)

    # 3. 儲存檔案
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    # 4. 將檔案路徑寫入資料庫
    db_deliverable = db_models.Deliverable(
        project_id=project_id,
        contractor_id=current_contractor.id,
        file_path=safe_filename # 只儲存檔名
    )
    db.add(db_deliverable)
    db.commit()
    db.refresh(db_deliverable)

    return {"filename": file.filename, "stored_filename": safe_filename, "id": db_deliverable.id}


# --- API 12: 刪除結案檔案 (接案人功能) [新功能] ---
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
        
    # 檢查專案狀態是否仍在 'in_progress'
    if db_deliverable.project.status != 'in_progress':
        raise HTTPException(status_code=400, detail="Cannot delete files from a project that is not in progress")

    # 3. 從硬碟刪除檔案
    file_path = os.path.join(UPLOAD_DIRECTORY, db_deliverable.file_path)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError as e:
        # 如果刪除失敗 (例如檔案被鎖定)，回報錯誤但繼續
        # (在生產環境中，這裡應該要有更詳細的日誌)
        print(f"Error deleting file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Could not delete file from server")

    # 4. 從資料庫刪除紀錄
    try:
        db.delete(db_deliverable)
        db.commit()
    except Exception as e:
        # 如果資料庫刪除失敗，我們應該... (理想上要 rollback 檔案刪除，但這裡簡化處理)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete file record from database: {e}")

    return {"message": "File deleted successfully"}