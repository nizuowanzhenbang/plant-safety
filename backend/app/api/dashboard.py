"""仪表盘 API"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.hazard import Hazard, HazardArea, HazardLevel, HazardStatus
from app.models.user import User
from app.utils.helpers import api_response

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """总览：总隐患数/待整改/超期/重大隐患/本月新增/本月关闭"""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 自动标记超期
    overdue_rows = db.query(Hazard).filter(
        Hazard.deadline.isnot(None),
        Hazard.deadline < now,
        Hazard.status.in_([HazardStatus.PENDING, HazardStatus.IN_PROGRESS]),
    ).all()
    for h in overdue_rows:
        h.status = HazardStatus.OVERDUE
    if overdue_rows:
        db.commit()

    total = db.query(func.count(Hazard.id)).scalar() or 0
    pending = db.query(func.count(Hazard.id)).filter(
        Hazard.status.in_([HazardStatus.PENDING, HazardStatus.IN_PROGRESS])
    ).scalar() or 0
    overdue = db.query(func.count(Hazard.id)).filter(Hazard.status == HazardStatus.OVERDUE).scalar() or 0
    major = db.query(func.count(Hazard.id)).filter(
        Hazard.level == HazardLevel.MAJOR,
        Hazard.status != HazardStatus.VERIFIED,
    ).scalar() or 0
    new_this_month = db.query(func.count(Hazard.id)).filter(Hazard.reported_at >= month_start).scalar() or 0
    closed_this_month = db.query(func.count(Hazard.id)).filter(
        Hazard.verified_at.isnot(None),
        Hazard.verified_at >= month_start,
    ).scalar() or 0

    rectification_rate = round((closed_this_month / new_this_month * 100), 1) if new_this_month else 0.0

    return api_response(data={
        "total_hazards": total,
        "pending_count": pending,
        "overdue_count": overdue,
        "major_count": major,
        "new_this_month": new_this_month,
        "closed_this_month": closed_this_month,
        "rectification_rate": rectification_rate,
    })


@router.get("/by-area")
def by_area(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """按区域统计未关闭隐患数"""
    rows = (
        db.query(Hazard.area, func.count(Hazard.id))
        .filter(Hazard.status != HazardStatus.VERIFIED)
        .group_by(Hazard.area)
        .all()
    )
    return api_response(data=[{"area": r[0].value if r[0] else "OTHER", "count": r[1]} for r in rows])


@router.get("/by-category")
def by_category(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """按类别统计"""
    rows = (
        db.query(Hazard.category, func.count(Hazard.id))
        .group_by(Hazard.category)
        .all()
    )
    return api_response(data=[{"category": r[0].value if r[0] else "OTHER", "count": r[1]} for r in rows])


@router.get("/trend")
def trend(days: int = Query(30, ge=7, le=180), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """每日新增隐患趋势"""
    start = datetime.utcnow() - timedelta(days=days)
    rows = db.query(Hazard).filter(Hazard.reported_at >= start).all()
    daily: dict = {}
    for h in rows:
        key = h.reported_at.strftime("%Y-%m-%d")
        if key not in daily:
            daily[key] = {"date": key, "general": 0, "major": 0}
        if h.level == HazardLevel.MAJOR:
            daily[key]["major"] += 1
        else:
            daily[key]["general"] += 1
    return api_response(data=sorted(daily.values(), key=lambda x: x["date"]))
