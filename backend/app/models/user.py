"""用户模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean
from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"           # 安环部主任
    SAFETY_OFFICER = "SAFETY_OFFICER"  # 安全员
    OPERATOR = "OPERATOR"     # 班组人员
    VIEWER = "VIEWER"         # 查看者


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    hashed_password = Column(String(200), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.OPERATOR, nullable=False)
    department = Column(String(50), nullable=True, comment="所属部门")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
