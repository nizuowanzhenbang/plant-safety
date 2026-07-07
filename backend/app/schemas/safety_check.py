"""安全检查 Pydantic schemas"""
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.models.safety_check import CheckFrequency, CheckPlanStatus, CheckRecordStatus
from app.models.hazard import HazardArea, HazardCategory, HazardLevel


class CheckItemTemplate(BaseModel):
    seq: int
    content: str
    standard: Optional[str] = None
    weight: Optional[float] = 1.0


class SafetyCheckPlanCreate(BaseModel):
    name: str
    area: HazardArea
    frequency: CheckFrequency
    owner_dept: str
    description: Optional[str] = None
    item_template: List[CheckItemTemplate]


class SafetyCheckPlanUpdate(BaseModel):
    name: Optional[str] = None
    area: Optional[HazardArea] = None
    frequency: Optional[CheckFrequency] = None
    owner_dept: Optional[str] = None
    description: Optional[str] = None
    item_template: Optional[List[CheckItemTemplate]] = None
    status: Optional[CheckPlanStatus] = None


class SafetyCheckPlanResponse(BaseModel):
    id: int
    name: str
    area: HazardArea
    frequency: CheckFrequency
    owner_dept: str
    description: Optional[str]
    item_template: List[CheckItemTemplate]
    status: CheckPlanStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GenerateRecordsRequest(BaseModel):
    """从计划批量生成检查记录"""
    plan_id: int
    scheduled_dates: List[date]


class CheckResultItem(BaseModel):
    seq: int
    content: str
    standard: Optional[str] = None
    conformant: bool
    notes: Optional[str] = None
    hazard_id: Optional[int] = None      # 已转隐患的 id


class StartCheckRequest(BaseModel):
    inspector: str


class SubmitCheckRequest(BaseModel):
    """提交检查结果"""
    inspector: str
    result_items: List[CheckResultItem]
    summary: Optional[str] = None


class ConvertHazardRequest(BaseModel):
    """把不符合项转隐患单"""
    seq: int                       # 检查记录中第几项
    category: HazardCategory       # 隐患类别
    level: HazardLevel             # 隐患等级
    assignee: Optional[str] = None
    assignee_dept: Optional[str] = None
    deadline_days: Optional[int] = None    # 不传按等级默认


class SafetyCheckRecordResponse(BaseModel):
    id: int
    record_code: str
    plan_id: int
    plan_name: Optional[str] = None
    area: Optional[HazardArea] = None
    scheduled_date: date
    inspector: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result_items: List[CheckResultItem] = []
    total_items: int
    nonconformant_count: int
    summary: Optional[str]
    status: CheckRecordStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
