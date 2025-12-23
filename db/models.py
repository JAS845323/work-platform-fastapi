# db/models.py

from sqlalchemy import Column, Integer, String, Text, ForeignKey, TIMESTAMP, Enum, NUMERIC, Boolean, Float, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base  # 從 db.py 匯入 Base

# --- [新增] 收藏關聯表 (多對多) ---
# 用於記錄使用者收藏了哪些專案
favorite_association = Table(
    'favorites', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    Column('project_id', Integer, ForeignKey('projects.id', ondelete="CASCADE"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum('client', 'contractor', name='user_role'), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # [優化] 評分統計欄位，用於商用級 Profile 顯示
    average_rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)

    # 建立關聯 (已修正原本字串格式的錯誤)
    projects_created = relationship("Project", back_populates="client", foreign_keys="Project.client_id")
    projects_assigned = relationship("Project", back_populates="contractor", foreign_keys="Project.selected_contractor_id")
    bids = relationship("Bid", back_populates="contractor")
    communications_sent = relationship("Communication", back_populates="sender")
    deliverables = relationship("Deliverable", back_populates="contractor")
    
    # [新增] 收藏功能關聯
    favorite_projects = relationship("Project", secondary=favorite_association, back_populates="favorited_by_users")

    # 評價關聯
    ratings_received = relationship("Rating", back_populates="to_user", foreign_keys="Rating.to_user_id")
    ratings_given = relationship("Rating", back_populates="from_user", foreign_keys="Rating.from_user_id")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(Enum('open', 'in_progress', 'completed', 'rejected', name='project_status'), nullable=False, default='open')
    selected_contractor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # 限時競標與預算
    deadline = Column(TIMESTAMP, nullable=True)
    budget = Column(Float, nullable=True)

    # 建立關聯
    client = relationship("User", back_populates="projects_created", foreign_keys=[client_id])
    contractor = relationship("User", back_populates="projects_assigned", foreign_keys=[selected_contractor_id])
    bids = relationship("Bid", back_populates="project", cascade="all, delete-orphan")
    communications = relationship("Communication", back_populates="project", cascade="all, delete-orphan")
    deliverables = relationship("Deliverable", back_populates="project", cascade="all, delete-orphan")
    
    # 評價、問題追蹤與收藏關聯
    ratings = relationship("Rating", back_populates="project", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="project", cascade="all, delete-orphan")
    favorited_by_users = relationship("User", secondary=favorite_association, back_populates="favorite_projects")

class Bid(Base):
    __tablename__ = "bids"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    contractor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bid_amount = Column(NUMERIC(10, 2), nullable=False)
    proposal_text = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # 提案計畫書路徑
    proposal_file_path = Column(String(512), nullable=True)

    # 建立關聯
    project = relationship("Project", back_populates="bids")
    contractor = relationship("User", back_populates="bids")

class Communication(Base):
    __tablename__ = "communications"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    is_read = Column(Boolean, default=False, nullable=False)

    # 建立關聯
    project = relationship("Project", back_populates="communications")
    sender = relationship("User", back_populates="communications_sent")

class Deliverable(Base):
    __tablename__ = "deliverables"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    contractor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_path = Column(String(512), nullable=False)
    uploaded_at = Column(TIMESTAMP, server_default=func.now())
    
    # 版本控管
    version = Column(Integer, default=1, nullable=False)

    # 建立關聯
    project = relationship("Project", back_populates="deliverables")
    contractor = relationship("User", back_populates="deliverables")

# --- 評價機制 ---
class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 對應星星評分的三個維度 (1-5分)
    score_dim1 = Column(Integer, nullable=False) 
    score_dim2 = Column(Integer, nullable=False)
    score_dim3 = Column(Integer, nullable=False)
    
    comment = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    project = relationship("Project", back_populates="ratings")
    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="ratings_given")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="ratings_received")

# --- Issue Tracker ---
class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    status = Column(Enum('open', 'resolved', name='issue_status'), default='open', nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    project = relationship("Project", back_populates="issues")
    creator = relationship("User", foreign_keys=[created_by_id])
    comments = relationship("IssueComment", back_populates="issue", cascade="all, delete-orphan")

class IssueComment(Base):
    __tablename__ = "issue_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    issue = relationship("Issue", back_populates="comments")
    sender = relationship("User", foreign_keys=[user_id])