"""隐患排查 API"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_min_role
from app.api.ws import push
from app.models.hazard import (
    Hazard,
    HazardArea,
    HazardCategory,
    HazardLevel,
    HazardStatus,
)
from app.models.user import User, UserRole
from app.schemas.hazard import (
    HazardCreate,
    HazardUpdate,
    HazardRectify,
    HazardVerify,
    HazardResponse,
)
from app.utils.helpers import api_response, paginate_response, generate_hazard_code

router = APIRouter(prefix="/api/hazards", tags=["隐患排查"])


@router.get("")
def list_hazards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    area: Optional[HazardArea] = None,
    category: Optional[HazardCategory] = None,
    level: Optional[HazardLevel] = None,
    status: Optional[HazardStatus] = None,
    keyword: Optional[str] = Query(None, description="标题/描述模糊查询"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Hazard)
    if area:
        q = q.filter(Hazard.area == area)
    if category:
        q = q.filter(Hazard.category == category)
    if level:
        q = q.filter(Hazard.level == level)
    if status:
        q = q.filter(Hazard.status == status)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter((Hazard.title.like(like)) | (Hazard.description.like(like)))

    total = q.count()
    rows = (
        q.order_by(Hazard.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [HazardResponse.model_validate(r).model_dump() for r in rows]
    return api_response(data=paginate_response(items, total, page, page_size))


@router.post("")
def create_hazard(
    payload: HazardCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    next_seq = (db.query(func.count(Hazard.id)).scalar() or 0) + 1
    hazard = Hazard(
        hazard_code=generate_hazard_code(next_seq),
        title=payload.title,
        description=payload.description,
        area=payload.area,
        category=payload.category,
        level=payload.level,
        reporter=payload.reporter,
        department=payload.department,
        reported_at=datetime.utcnow(),
        photo_url=payload.photo_url,
        assignee=payload.assignee,
        assignee_dept=payload.assignee_dept,
        deadline=payload.deadline,
        status=HazardStatus.IN_PROGRESS if payload.assignee else HazardStatus.PENDING,
    )
    db.add(hazard)
    db.commit()
    db.refresh(hazard)
    background_tasks.add_task(
        push,
        "hazard.created",
        "新增隐患",
        f"{hazard.hazard_code} {hazard.title}",
        {"id": hazard.id, "level": hazard.level.value, "area": hazard.area.value},
    )
    return api_response(message="隐患已登记", data=HazardResponse.model_validate(hazard).model_dump())


@router.get("/{hazard_id}")
def get_hazard(hazard_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    h = db.query(Hazard).filter(Hazard.id == hazard_id).first()
    if not h:
        raise HTTPException(404, "隐患不存在")
    return api_response(data=HazardResponse.model_validate(h).model_dump())


@router.put("/{hazard_id}")
def update_hazard(
    hazard_id: int,
    payload: HazardUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    h = db.query(Hazard).filter(Hazard.id == hazard_id).first()
    if not h:
        raise HTTPException(404, "隐患不存在")
    if h.status in (HazardStatus.VERIFIED,):
        raise HTTPException(400, "已关闭隐患不可修改")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(h, field, value)
    if payload.assignee and h.status == HazardStatus.PENDING:
        h.status = HazardStatus.IN_PROGRESS
    db.commit()
    db.refresh(h)
    return api_response(message="已更新", data=HazardResponse.model_validate(h).model_dump())


@router.post("/{hazard_id}/rectify")
def rectify_hazard(
    hazard_id: int,
    payload: HazardRectify,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    """提交整改完成（待复查）"""
    h = db.query(Hazard).filter(Hazard.id == hazard_id).first()
    if not h:
        raise HTTPException(404, "隐患不存在")
    if h.status == HazardStatus.VERIFIED:
        raise HTTPException(400, "隐患已关闭")
    h.rectification_measure = payload.rectification_measure
    h.rectified_at = payload.rectified_at or datetime.utcnow()
    h.status = HazardStatus.RECTIFIED
    db.commit()
    db.refresh(h)
    background_tasks.add_task(
        push,
        "hazard.rectified",
        "隐患待复查",
        f"{h.hazard_code} {h.title} 整改完成，待复查",
        {"id": h.id},
    )
    return api_response(message="整改已提交，等待复查", data=HazardResponse.model_validate(h).model_dump())


@router.post("/{hazard_id}/verify")
def verify_hazard(
    hazard_id: int,
    payload: HazardVerify,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current: User = Depends(require_min_role(UserRole.SAFETY_OFFICER)),
):
    """复查：通过则关闭，未通过则退回整改中"""
    h = db.query(Hazard).filter(Hazard.id == hazard_id).first()
    if not h:
        raise HTTPException(404, "隐患不存在")
    if h.status != HazardStatus.RECTIFIED:
        raise HTTPException(400, "仅已整改的隐患可以复查")
    h.verifier = payload.verifier
    h.verification_notes = payload.verification_notes
    h.verified_at = datetime.utcnow()
    h.status = HazardStatus.VERIFIED if payload.passed else HazardStatus.IN_PROGRESS
    if not payload.passed:
        h.rectified_at = None
    db.commit()
    db.refresh(h)
    background_tasks.add_task(
        push,
        "hazard.verified" if payload.passed else "hazard.rejected",
        "隐患复查通过" if payload.passed else "复查退回",
        f"{h.hazard_code} {h.title}",
        {"id": h.id, "passed": payload.passed},
    )
    return api_response(
        message="复查通过，隐患已关闭" if payload.passed else "复查未通过，退回整改",
        data=HazardResponse.model_validate(h).model_dump(),
    )
