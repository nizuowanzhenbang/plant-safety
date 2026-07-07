"""两票管理模型：工作票 + 操作票

发电厂"两票"是日常作业的核心安全凭证：
- 工作票（GZ-）：检修类作业的安全审批与许可单据，含安全措施、风险点、监护人。
- 操作票（CZ-）：倒闸/启停设备等运行类作业的预先编制操作步骤清单，逐项执行勾对。
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class WorkTicketType(str, enum.Enum):
    """工作票类型"""
    ELECTRICAL_FIRST = "ELECTRICAL_FIRST"     # 电气第一种工作票（停电）
    ELECTRICAL_SECOND = "ELECTRICAL_SECOND"   # 电气第二种工作票（不停电）
    THERMAL = "THERMAL"                       # 热力机械工作票
    HOT_WORK = "HOT_WORK"                     # 动火工作票
    CONFINED_SPACE = "CONFINED_SPACE"         # 有限空间作业票
    HIGH_ALTITUDE = "HIGH_ALTITUDE"           # 高处作业票


class WorkTicketStatus(str, enum.Enum):
    """工作票状态机：草稿 → 待审批 → 已许可 → 已开工 → 已收工 → 已终结
    任意阶段可作废 CANCELLED。
    """
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"               # 已许可
    IN_PROGRESS = "IN_PROGRESS"         # 已开工
    SUSPENDED = "SUSPENDED"             # 已收工待复工
    COMPLETED = "COMPLETED"             # 已终结
    CANCELLED = "CANCELLED"


class WorkTicket(Base):
    """工作票"""
    __tablename__ = "work_tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_code = Column(String(50), unique=True, index=True, nullable=False, comment="工作票号 GZ-YYYYMMDD-NNNN")

    ticket_type = Column(Enum(WorkTicketType), nullable=False, comment="工作票类型")
    title = Column(String(200), nullable=False, comment="工作内容标题")
    work_content = Column(Text, nullable=False, comment="具体工作内容")
    work_location = Column(String(200), nullable=False, comment="工作地点")

    # 人员
    issuer = Column(String(50), nullable=False, comment="签发人")
    work_leader = Column(String(50), nullable=False, comment="工作负责人")
    work_members = Column(Text, nullable=True, comment="工作班成员（逗号分隔）")
    supervisor = Column(String(50), nullable=True, comment="监护人")
    permitter = Column(String(50), nullable=True, comment="许可人（运行值班员）")

    # 时间
    planned_start = Column(DateTime, nullable=False, comment="计划开始时间")
    planned_end = Column(DateTime, nullable=False, comment="计划结束时间")
    actual_start = Column(DateTime, nullable=True, comment="实际开工时间")
    actual_end = Column(DateTime, nullable=True, comment="实际收工时间")

    # 安全措施 / 风险点
    safety_measures = Column(Text, nullable=False, comment="安全措施清单（多行）")
    risk_points = Column(Text, nullable=True, comment="危险点分析")

    # 审批
    approver = Column(String(50), nullable=True, comment="审批人（安全员）")
    approved_at = Column(DateTime, nullable=True)
    approval_notes = Column(Text, nullable=True)

    # 终结
    closer = Column(String(50), nullable=True, comment="终结人")
    closed_at = Column(DateTime, nullable=True)
    close_notes = Column(Text, nullable=True, comment="终结说明")

    status = Column(Enum(WorkTicketStatus), default=WorkTicketStatus.DRAFT, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OperationTicketStatus(str, enum.Enum):
    """操作票状态机：草稿 → 待审核 → 待执行 → 执行中 → 已完成
    任意阶段可作废 CANCELLED。
    """
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    READY = "READY"               # 审核通过，待执行
    EXECUTING = "EXECUTING"       # 执行中
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class OperationTicket(Base):
    """操作票（倒闸/启停等运行操作）"""
    __tablename__ = "operation_tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_code = Column(String(50), unique=True, index=True, nullable=False, comment="操作票号 CZ-YYYYMMDD-NNNN")

    title = Column(String(200), nullable=False, comment="操作任务（如：1号机组并网操作）")
    operation_target = Column(String(200), nullable=False, comment="操作设备/系统")

    # 人员
    operator = Column(String(50), nullable=False, comment="操作人")
    supervisor = Column(String(50), nullable=False, comment="监护人")
    issuer = Column(String(50), nullable=False, comment="发令人/值长")
    reviewer = Column(String(50), nullable=True, comment="审核人")

    # 时间
    planned_at = Column(DateTime, nullable=False, comment="计划操作时间")
    started_at = Column(DateTime, nullable=True, comment="开始执行时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")

    # 操作步骤（JSON 文本，每条 {step, content, done, checked_at}）
    steps = Column(Text, nullable=False, comment="操作步骤列表，JSON 字符串")

    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)

    status = Column(Enum(OperationTicketStatus), default=OperationTicketStatus.DRAFT, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
