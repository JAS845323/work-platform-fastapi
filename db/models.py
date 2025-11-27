# db/models.py

# *** 這是【已修正】的第一行，加入了 Boolean ***
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, TIMESTAMP, Enum, NUMERIC, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base  # 從 db.py 匯入 Base

# -------------------------------------------------
# 注意:
# 這些 Enum 名稱 ('user_role', 'project_status')
# 必須與你在 SQL 中 CREATE TYPE 的名稱完全一致
# -------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum('client', 'contractor', name='user_role'), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # 建立關聯 (Relationships)
    projects_created = relationship("Project", back_populates="client", foreign_keys="[Project.client_id]")
    projects_assigned = relationship("Project", back_populates="contractor", foreign_keys="[Project.selected_contractor_id]")
    bids = relationship("Bid", back_populates="contractor")
    communications_sent = relationship("Communication", back_populates="sender")
    deliverables = relationship("Deliverable", back_populates="contractor")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(Enum('open', 'in_progress', 'completed', 'rejected', name='project_status'), nullable=False, default='open')
    selected_contractor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # 建立關聯
    client = relationship("User", back_populates="projects_created", foreign_keys=[client_id])
    contractor = relationship("User", back_populates="projects_assigned", foreign_keys=[selected_contractor_id])
    bids = relationship("Bid", back_populates="project", cascade="all, delete-orphan")
    communications = relationship("Communication", back_populates="project", cascade="all, delete-orphan")
    deliverables = relationship("Deliverable", back_populates="project", cascade="all, delete-orphan")

class Bid(Base):
    __tablename__ = "bids"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    contractor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bid_amount = Column(NUMERIC(10, 2), nullable=False)
    proposal_text = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())

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
    
    # *** 這是你 20 萬獎金的新欄位 ***
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

    # 建立關聯
    project = relationship("Project", back_populates="deliverables")
    contractor = relationship("User", back_populates="deliverables")