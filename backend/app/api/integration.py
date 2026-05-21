"""跨系统集成接口：接收 equipment-inspection 推送的 CRITICAL 缺陷，落地为隐患单"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import func
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.models.hazard import (
    Hazard, HazardArea, HazardCategory, HazardLevel, HazardStatus,
)
from app.utils.helpers import api_response, generate_hazard_code
from fastapi import Depends

router = APIRouter(prefix="/api/integration", tags=["跨系统集成"])


class IncomingHazard(BaseModel):
    external_no: str                     # 对方系统的单号（缺陷号）
    source_system: str = "equipment-inspection"
    title: str
    description: Optional[str] = None
    severity: str                        # MINOR/MAJOR/CRITICAL
    equipment_code: Optional[str] = None
    equipment_name: Optional[str] = None
    location: Optional[str] = None
    reported_by: Optional[str] = None
    reported_at: Optional[datetime] = None
    sla_deadline: Optional[datetime] = None
    model_config = ConfigDict(extra="ignore")


def _verify_secret(secret: Optional[str]) -> None:
    if not secret or secret != settings.INTEGRATION_SECRET:
        raise HTTPException(status_code=401, detail="INTEGRATION_SECRET 校验失败")


def _map_area(equipment_code: Optional[str]) -> HazardArea:
    """根据设备编号前缀粗略映射隐患发生区域。"""
    if not equipment_code:
        return HazardArea.MAIN_PLANT
    code = equipment_code.upper()
    if "-BL-" in code:
        return HazardArea.BOILER
    if "-TB-" in code:
        return HazardArea.TURBINE
    if "-GN-" in code or "-EL-" in code:
        return HazardArea.ELECTRICAL
    if "-CH-" in code:
        return HazardArea.CHEMICAL
    if "-AS-" in code:
        return HazardArea.ASH_HANDLING
    if "-DS-" in code:
        return HazardArea.DESULFURIZATION
    return HazardArea.MAIN_PLANT


def _map_level(severity: str) -> HazardLevel:
    return HazardLevel.MAJOR if severity.upper() == "CRITICAL" else HazardLevel.GENERAL


@router.post("/hazards")
def receive_hazard(
    payload: IncomingHazard,
    db: Session = Depends(get_db),
    x_integration_secret: Optional[str] = Header(None, alias="X-Integration-Secret"),
):
    """接收外部系统推送的隐患单（幂等：external_source + external_no 唯一）。

    返回 plant-safety 内部隐患号 hazard_no（即 hazard_code），
    供对方系统写回 `safety_hazard_no` 字段。
    """
    _verify_secret(x_integration_secret)

    # 幂等：若已存在直接返回
    existing = (
        db.query(Hazard)
        .filter(
            Hazard.external_source == payload.source_system,
            Hazard.external_no == payload.external_no,
        )
        .first()
    )
    if existing:
        return api_response(
            message="已存在，幂等返回",
            data={"hazard_no": existing.hazard_code, "id": existing.id, "duplicated": True},
        )

    next_seq = (db.query(func.count(Hazard.id)).scalar() or 0) + 1
    code = generate_hazard_code(next_seq)

    level = _map_level(payload.severity)
    # CRITICAL → MAJOR 隐患：14 天整改；一般 30 天
    deadline_days = 14 if level == HazardLevel.MAJOR else 30
    deadline = (payload.reported_at or datetime.utcnow()) + timedelta(days=deadline_days)

    desc_parts = [payload.description or payload.title]
    if payload.equipment_code:
        desc_parts.append(f"[来源] {payload.source_system} 单号 {payload.external_no}")
        desc_parts.append(f"[设备] {payload.equipment_code} {payload.equipment_name or ''}")
    full_desc = "\n".join(desc_parts)

    h = Hazard(
        hazard_code=code,
        title=f"[联动] {payload.title}"[:200],
        description=full_desc,
        area=_map_area(payload.equipment_code),
        category=HazardCategory.MECHANICAL,
        level=level,
        reporter=payload.reported_by or "external-integration",
        department=payload.source_system,
        reported_at=payload.reported_at or datetime.utcnow(),
        deadline=deadline,
        status=HazardStatus.PENDING,
        external_source=payload.source_system,
        external_no=payload.external_no,
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    return api_response(
        message="已建隐患单",
        data={"hazard_no": h.hazard_code, "id": h.id, "duplicated": False},
    )


@router.get("/hazards/by-external/{source}/{external_no}")
def lookup_by_external(
    source: str, external_no: str,
    db: Session = Depends(get_db),
    x_integration_secret: Optional[str] = Header(None, alias="X-Integration-Secret"),
):
    """根据外部 source + external_no 反查隐患单"""
    _verify_secret(x_integration_secret)
    h = db.query(Hazard).filter(
        Hazard.external_source == source,
        Hazard.external_no == external_no,
    ).first()
    if not h:
        raise HTTPException(404, "未找到")
    return api_response(data={
        "hazard_no": h.hazard_code,
        "id": h.id,
        "status": h.status.value if hasattr(h.status, "value") else h.status,
        "deadline": h.deadline.isoformat() if h.deadline else None,
        "rectified_at": h.rectified_at.isoformat() if h.rectified_at else None,
    })
