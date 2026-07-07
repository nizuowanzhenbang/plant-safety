"""两票 Pydantic schemas"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.models.ticket import (
    WorkTicketType, WorkTicketStatus, OperationTicketStatus,
)


# ============== 工作票 ==============

class WorkTicketCreate(BaseModel):
    ticket_type: WorkTicketType
    title: str
    work_content: str
    work_location: str
    issuer: str
    work_leader: str
    work_members: Optional[str] = None
    supervisor: Optional[str] = None
    planned_start: datetime
    planned_end: datetime
    safety_measures: str
    risk_points: Optional[str] = None


class WorkTicketUpdate(BaseModel):
    title: Optional[str] = None
    work_content: Optional[str] = None
    work_location: Optional[str] = None
    work_leader: Optional[str] = None
    work_members: Optional[str] = None
    supervisor: Optional[str] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    safety_measures: Optional[str] = None
    risk_points: Optional[str] = None


class WorkTicketApprove(BaseModel):
    approval_notes: Optional[str] = None
    approved: bool = True  # False 退回草稿


class WorkTicketPermit(BaseModel):
    """许可（运行值班员开工许可）"""
    permitter: str


class WorkTicketStartFinish(BaseModel):
    """开工 / 收工 / 终结的备注"""
    notes: Optional[str] = None


class WorkTicketClose(BaseModel):
    closer: str
    close_notes: Optional[str] = None


class WorkTicketResponse(BaseModel):
    id: int
    ticket_code: str
    ticket_type: WorkTicketType
    title: str
    work_content: str
    work_location: str
    issuer: str
    work_leader: str
    work_members: Optional[str]
    supervisor: Optional[str]
    permitter: Optional[str]
    planned_start: datetime
    planned_end: datetime
    actual_start: Optional[datetime]
    actual_end: Optional[datetime]
    safety_measures: str
    risk_points: Optional[str]
    approver: Optional[str]
    approved_at: Optional[datetime]
    approval_notes: Optional[str]
    closer: Optional[str]
    closed_at: Optional[datetime]
    close_notes: Optional[str]
    status: WorkTicketStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============== 操作票 ==============

class OperationStep(BaseModel):
    step: int
    content: str
    done: bool = False
    checked_at: Optional[datetime] = None
    notes: Optional[str] = None


class OperationTicketCreate(BaseModel):
    title: str
    operation_target: str
    operator: str
    supervisor: str
    issuer: str
    planned_at: datetime
    steps: List[OperationStep]


class OperationTicketUpdate(BaseModel):
    title: Optional[str] = None
    operation_target: Optional[str] = None
    operator: Optional[str] = None
    supervisor: Optional[str] = None
    issuer: Optional[str] = None
    planned_at: Optional[datetime] = None
    steps: Optional[List[OperationStep]] = None


class OperationTicketReview(BaseModel):
    reviewer: str
    approved: bool = True
    review_notes: Optional[str] = None


class OperationStepCheck(BaseModel):
    """单步勾对"""
    step: int
    notes: Optional[str] = None


class OperationTicketResponse(BaseModel):
    id: int
    ticket_code: str
    title: str
    operation_target: str
    operator: str
    supervisor: str
    issuer: str
    reviewer: Optional[str]
    planned_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    steps: List[OperationStep]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    status: OperationTicketStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
