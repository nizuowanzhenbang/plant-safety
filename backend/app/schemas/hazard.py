"""隐患相关 Pydantic schemas"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models.hazard import HazardArea, HazardCategory, HazardLevel, HazardStatus


class HazardCreate(BaseModel):
    title: str
    description: str
    area: HazardArea
    category: HazardCategory
    level: HazardLevel
    reporter: str
    department: Optional[str] = None
    photo_url: Optional[str] = None
    assignee: Optional[str] = None
    assignee_dept: Optional[str] = None
    deadline: Optional[datetime] = None


class HazardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    area: Optional[HazardArea] = None
    category: Optional[HazardCategory] = None
    level: Optional[HazardLevel] = None
    assignee: Optional[str] = None
    assignee_dept: Optional[str] = None
    deadline: Optional[datetime] = None
    rectification_measure: Optional[str] = None


class HazardRectify(BaseModel):
    """提交整改完成"""
    rectification_measure: str
    rectified_at: Optional[datetime] = None


class HazardVerify(BaseModel):
    """复查确认"""
    verifier: str
    verification_notes: str
    passed: bool  # 是否通过复查


class HazardResponse(BaseModel):
    id: int
    hazard_code: str
    title: str
    description: str
    area: HazardArea
    category: HazardCategory
    level: HazardLevel
    reporter: str
    department: Optional[str]
    reported_at: datetime
    photo_url: Optional[str]
    assignee: Optional[str]
    assignee_dept: Optional[str]
    deadline: Optional[datetime]
    rectification_measure: Optional[str]
    rectified_at: Optional[datetime]
    verifier: Optional[str]
    verified_at: Optional[datetime]
    verification_notes: Optional[str]
    status: HazardStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
