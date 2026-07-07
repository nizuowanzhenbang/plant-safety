"""工作票 API：草稿 → 待审批 → 已许可 → 已开工 → 已收工 → 已终结"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_min_role
from app.api.ws import push
from app.models.ticket import WorkTicket, WorkTicketType, WorkTicketStatus
from app.models.user import User, UserRole
from app.schemas.ticket import (
    WorkTicketCreate, WorkTicketUpdate, WorkTicketApprove,
    WorkTicketPermit, WorkTicketStartFinish, WorkTicketClose,
    WorkTicketResponse,
)
from app.utils.helpers import api_response, paginate_response, generate_work_ticket_code

router = APIRouter(prefix="/api/work-tickets", tags=["工作票"])


@router.get("")
def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ticket_type: Optional[WorkTicketType] = None,
    status: Optional[WorkTicketStatus] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(WorkTicket)
    if ticket_type:
        q = q.filter(WorkTicket.ticket_type == ticket_type)
    if status:
        q = q.filter(WorkTicket.status == status)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            (WorkTicket.title.like(like)) |
            (WorkTicket.work_content.like(like)) |
            (WorkTicket.work_location.like(like))
        )
    total = q.count()
    rows = q.order_by(WorkTicket.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [WorkTicketResponse.model_validate(r).model_dump() for r in rows]
    return api_response(data=paginate_response(items, total, page, page_size))


@router.post("")
def create_ticket(
    payload: WorkTicketCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    if payload.planned_end <= payload.planned_start:
        raise HTTPException(400, "计划结束时间必须晚于开始时间")
    seq = (db.query(func.count(WorkTicket.id)).scalar() or 0) + 1
    t = WorkTicket(
        ticket_code=generate_work_ticket_code(seq),
        ticket_type=payload.ticket_type,
        title=payload.title,
        work_content=payload.work_content,
        work_location=payload.work_location,
        issuer=payload.issuer,
        work_leader=payload.work_leader,
        work_members=payload.work_members,
        supervisor=payload.supervisor,
        planned_start=payload.planned_start,
        planned_end=payload.planned_end,
        safety_measures=payload.safety_measures,
        risk_points=payload.risk_points,
        status=WorkTicketStatus.DRAFT,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return api_response(message="工作票草稿已创建", data=WorkTicketResponse.model_validate(t).model_dump())


@router.get("/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    t = db.query(WorkTicket).filter(WorkTicket.id == ticket_id).first()
    if not t:
        raise HTTPException(404, "工作票不存在")
    return api_response(data=WorkTicketResponse.model_validate(t).model_dump())


@router.put("/{ticket_id}")
def update_ticket(
    ticket_id: int,
    payload: WorkTicketUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    t = db.query(WorkTicket).filter(WorkTicket.id == ticket_id).first()
    if not t:
        raise HTTPException(404, "工作票不存在")
    if t.status != WorkTicketStatus.DRAFT:
        raise HTTPException(400, "仅草稿状态可编辑")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(t, field, value)
    db.commit()
    db.refresh(t)
    return api_response(message="已更新", data=WorkTicketResponse.model_validate(t).model_dump())


@router.post("/{ticket_id}/submit")
def submit_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    """提交审批：草稿 → 待审批"""
    t = _require_status(db, ticket_id, WorkTicketStatus.DRAFT, "仅草稿可提交")
    t.status = WorkTicketStatus.PENDING_APPROVAL
    db.commit()
    db.refresh(t)
    return api_response(message="已提交审批", data=WorkTicketResponse.model_validate(t).model_dump())


@router.post("/{ticket_id}/approve")
def approve_ticket(
    ticket_id: int,
    payload: WorkTicketApprove,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current: User = Depends(require_min_role(UserRole.SAFETY_OFFICER)),
):
    """审批：待审批 → 已许可 / 退回草稿"""
    t = _require_status(db, ticket_id, WorkTicketStatus.PENDING_APPROVAL, "仅待审批状态可审批")
    t.approver = current.username
    t.approved_at = datetime.utcnow()
    t.approval_notes = payload.approval_notes
    t.status = WorkTicketStatus.APPROVED if payload.approved else WorkTicketStatus.DRAFT
    db.commit()
    db.refresh(t)
    background_tasks.add_task(
        push,
        "work_ticket.approved" if payload.approved else "work_ticket.rejected",
        "工作票审批通过" if payload.approved else "工作票审批退回",
        f"{t.ticket_code} {t.title}",
        {"id": t.id, "ticket_code": t.ticket_code},
    )
    return api_response(
        message="审批通过，已许可" if payload.approved else "审批退回草稿",
        data=WorkTicketResponse.model_validate(t).model_dump(),
    )


@router.post("/{ticket_id}/start")
def start_ticket(
    ticket_id: int,
    payload: WorkTicketPermit,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    """开工许可 + 实际开工：已许可 → 已开工"""
    t = _require_status(db, ticket_id, WorkTicketStatus.APPROVED, "仅已许可工作票可开工")
    t.permitter = payload.permitter
    t.actual_start = datetime.utcnow()
    t.status = WorkTicketStatus.IN_PROGRESS
    db.commit()
    db.refresh(t)
    return api_response(message="已开工", data=WorkTicketResponse.model_validate(t).model_dump())


@router.post("/{ticket_id}/finish")
def finish_ticket(
    ticket_id: int,
    payload: WorkTicketClose,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    """终结：已开工 → 已终结"""
    t = _require_status(db, ticket_id, WorkTicketStatus.IN_PROGRESS, "仅已开工工作票可终结")
    t.closer = payload.closer
    t.close_notes = payload.close_notes
    t.closed_at = datetime.utcnow()
    t.actual_end = t.actual_end or t.closed_at
    t.status = WorkTicketStatus.COMPLETED
    db.commit()
    db.refresh(t)
    background_tasks.add_task(
        push, "work_ticket.completed", "工作票已终结",
        f"{t.ticket_code} {t.title}", {"id": t.id},
    )
    return api_response(message="工作票已终结", data=WorkTicketResponse.model_validate(t).model_dump())


@router.post("/{ticket_id}/cancel")
def cancel_ticket(
    ticket_id: int,
    payload: WorkTicketStartFinish,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.SAFETY_OFFICER)),
):
    """作废（任意非完成态均可作废）"""
    t = db.query(WorkTicket).filter(WorkTicket.id == ticket_id).first()
    if not t:
        raise HTTPException(404, "工作票不存在")
    if t.status in (WorkTicketStatus.COMPLETED, WorkTicketStatus.CANCELLED):
        raise HTTPException(400, "已终结或已作废，不可再作废")
    t.status = WorkTicketStatus.CANCELLED
    t.close_notes = payload.notes
    t.closed_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return api_response(message="工作票已作废", data=WorkTicketResponse.model_validate(t).model_dump())


def _require_status(db: Session, ticket_id: int, expected: WorkTicketStatus, msg: str) -> WorkTicket:
    t = db.query(WorkTicket).filter(WorkTicket.id == ticket_id).first()
    if not t:
        raise HTTPException(404, "工作票不存在")
    if t.status != expected:
        raise HTTPException(400, msg)
    return t
