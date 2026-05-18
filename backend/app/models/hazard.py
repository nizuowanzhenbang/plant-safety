"""隐患排查模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class HazardArea(str, enum.Enum):
    """隐患发生区域（发电厂分区）"""
    MAIN_PLANT = "MAIN_PLANT"             # 主厂房
    BOILER = "BOILER"                     # 锅炉区
    TURBINE = "TURBINE"                   # 汽轮机区
    ELECTRICAL = "ELECTRICAL"             # 电气区/升压站
    FUEL = "FUEL"                         # 燃料区/输煤
    CHEMICAL = "CHEMICAL"                 # 化学水/水处理
    ASH_HANDLING = "ASH_HANDLING"         # 除灰除渣
    DESULFURIZATION = "DESULFURIZATION"   # 脱硫脱硝
    COOLING_TOWER = "COOLING_TOWER"       # 冷却塔
    SWITCHYARD = "SWITCHYARD"             # 开关站
    OFFICE = "OFFICE"                     # 办公区
    OTHER = "OTHER"


class HazardCategory(str, enum.Enum):
    """隐患类别（按作业风险分类）"""
    ELECTRICAL_SAFETY = "ELECTRICAL_SAFETY"     # 电气安全
    PRESSURE_VESSEL = "PRESSURE_VESSEL"         # 锅炉压力容器
    CHEMICAL_HAZARD = "CHEMICAL_HAZARD"         # 危险化学品
    WORK_AT_HEIGHT = "WORK_AT_HEIGHT"           # 高处作业
    CONFINED_SPACE = "CONFINED_SPACE"           # 有限空间
    HOT_WORK = "HOT_WORK"                       # 动火作业
    LIFTING = "LIFTING"                         # 起重作业
    RADIATION = "RADIATION"                     # 辐射防护
    FIRE_PROTECTION = "FIRE_PROTECTION"         # 消防安全
    MECHANICAL = "MECHANICAL"                   # 机械伤害
    ENVIRONMENTAL = "ENVIRONMENTAL"             # 环境/排放
    HOUSEKEEPING = "HOUSEKEEPING"               # 现场环境
    OTHER = "OTHER"


class HazardLevel(str, enum.Enum):
    """隐患等级"""
    GENERAL = "GENERAL"         # 一般隐患
    MAJOR = "MAJOR"             # 重大隐患


class HazardStatus(str, enum.Enum):
    """隐患处理状态"""
    PENDING = "PENDING"             # 待整改
    IN_PROGRESS = "IN_PROGRESS"     # 整改中
    RECTIFIED = "RECTIFIED"         # 已整改（待复查）
    VERIFIED = "VERIFIED"           # 已复查关闭
    OVERDUE = "OVERDUE"             # 超期未整改


class Hazard(Base):
    """隐患排查记录"""
    __tablename__ = "hazards"

    id = Column(Integer, primary_key=True, index=True)
    hazard_code = Column(String(50), unique=True, index=True, nullable=False, comment="隐患编号")

    # 基本信息
    title = Column(String(200), nullable=False, comment="隐患标题")
    description = Column(Text, nullable=False, comment="详细描述")
    area = Column(Enum(HazardArea), nullable=False, comment="发生区域")
    category = Column(Enum(HazardCategory), nullable=False, comment="隐患类别")
    level = Column(Enum(HazardLevel), nullable=False, comment="隐患等级")

    # 发现信息
    reporter = Column(String(50), nullable=False, comment="发现人")
    department = Column(String(50), nullable=True, comment="发现部门")
    reported_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="发现时间")
    photo_url = Column(String(500), nullable=True, comment="现场照片URL")

    # 整改信息
    assignee = Column(String(50), nullable=True, comment="整改责任人")
    assignee_dept = Column(String(50), nullable=True, comment="整改部门")
    deadline = Column(DateTime, nullable=True, comment="整改期限")
    rectification_measure = Column(Text, nullable=True, comment="整改措施")
    rectified_at = Column(DateTime, nullable=True, comment="整改完成时间")

    # 复查信息
    verifier = Column(String(50), nullable=True, comment="复查人")
    verified_at = Column(DateTime, nullable=True, comment="复查时间")
    verification_notes = Column(Text, nullable=True, comment="复查意见")

    # 状态
    status = Column(Enum(HazardStatus), default=HazardStatus.PENDING, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
