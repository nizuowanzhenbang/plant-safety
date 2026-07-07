"""安全检查模块：检查计划 + 检查记录 + 不符合项

支持周期性检查（日常巡查 / 周检 / 月检 / 季度检 / 年度检）。
执行检查时勾选每个检查项是否符合，不符合项可一键转隐患单。
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, Boolean, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.database import Base


class CheckFrequency(str, enum.Enum):
    """检查周期"""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"
    ADHOC = "ADHOC"     # 临时


class CheckPlanStatus(str, enum.Enum):
    """检查计划状态"""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"


class SafetyCheckPlan(Base):
    """安全检查计划：模板（含若干检查项），按周期产生 SafetyCheckRecord"""
    __tablename__ = "safety_check_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="检查计划名称")
    area = Column(String(50), nullable=False, comment="检查区域，沿用 HazardArea 枚举值")
    frequency = Column(Enum(CheckFrequency), nullable=False)
    owner_dept = Column(String(50), nullable=False, comment="责任部门")
    description = Column(Text, nullable=True)

    # 检查项模板：JSON 列表，每项 {seq, content, standard, weight}
    item_template = Column(Text, nullable=False, comment="检查项模板 JSON")

    status = Column(Enum(CheckPlanStatus), default=CheckPlanStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    records = relationship("SafetyCheckRecord", back_populates="plan", cascade="all, delete-orphan")


class CheckRecordStatus(str, enum.Enum):
    """检查记录状态"""
    PENDING = "PENDING"             # 待执行
    IN_PROGRESS = "IN_PROGRESS"     # 检查中
    COMPLETED = "COMPLETED"         # 已完成
    OVERDUE = "OVERDUE"             # 超期未执行


class SafetyCheckRecord(Base):
    """单次安全检查执行记录"""
    __tablename__ = "safety_check_records"

    id = Column(Integer, primary_key=True, index=True)
    record_code = Column(String(50), unique=True, index=True, nullable=False, comment="检查编号 AJ-YYYYMMDD-NNNN")
    plan_id = Column(Integer, ForeignKey("safety_check_plans.id"), nullable=False)

    scheduled_date = Column(Date, nullable=False, comment="计划检查日期")
    inspector = Column(String(50), nullable=True, comment="检查人")

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # 检查结果：JSON 列表，每项 {seq, content, standard, conformant, notes, hazard_id}
    result_items = Column(Text, nullable=True, comment="逐项结果 JSON")

    total_items = Column(Integer, default=0, comment="检查项总数")
    nonconformant_count = Column(Integer, default=0, comment="不符合项数")
    summary = Column(Text, nullable=True, comment="检查结论")

    status = Column(Enum(CheckRecordStatus), default=CheckRecordStatus.PENDING, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plan = relationship("SafetyCheckPlan", back_populates="records")
