"""操作票 API：草稿 → 待审核 → 待执行 → 执行中 → 已完成"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_min_role
from app.api.ws import push
from app.models.ticket import OperationTicket, OperationTicketStatus
from app.models.user import User, UserRole
from app.schemas.ticket import (
    OperationStep, OperationTicketCreate, OperationTicketUpdate,
    OperationTicketReview, OperationStepCheck, OperationTicketResponse,
)
from app.utils.helpers import api_response, paginate_response, generate_operation_ticket_code

router = APIRouter(prefix="/api/operation-tickets", tags=["操作票"])


def _ticket_to_response(t: OperationTicket) -> dict:
    """把模型转响应（steps 反序列化 JSON）"""
    data = {
        "id": t.id, "ticket_code": t.ticket_code, "title": t.title,
        "operation_target": t.operation_target, "operator": t.operator,
        "supervisor": t.supervisor, "issuer": t.issuer, "reviewer": t.reviewer,
        "planned_at": t.planned_at, "started_at": t.started_at,
        "completed_at": t.completed_at,
        "steps": json.loads(t.steps) if t.steps else [],
        "reviewed_at": t.reviewed_at, "review_notes": t.review_notes,
        "status": t.status, "created_at": t.created_at, "updated_at": t.updated_at,
    }
    return OperationTicketResponse.model_validate(data).model_dump()


@router.get("")
def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[OperationTicketStatus] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(OperationTicket)
    if status:
        q = q.filter(OperationTicket.status == status)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            (OperationTicket.title.like(like)) |
            (OperationTicket.operation_target.like(like))
        )
    total = q.count()
    rows = q.order_by(OperationTicket.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [_ticket_to_response(r) for r in rows]
    return api_response(data=paginate_response(items, total, page, page_size))


@router.post("")
def create_ticket(
    payload: OperationTicketCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    if not payload.steps:
        raise HTTPException(400, "操作步骤不能为空")
    seq = (db.query(func.count(OperationTicket.id)).scalar() or 0) + 1
    t = OperationTicket(
        ticket_code=generate_operation_ticket_code(seq),
        title=payload.title,
        operation_target=payload.operation_target,
        operator=payload.operator,
        supervisor=payload.supervisor,
        issuer=payload.issuer,
        planned_at=payload.planned_at,
        steps=json.dumps([s.model_dump(mode="json") for s in payload.steps], ensure_ascii=False),
        status=OperationTicketStatus.DRAFT,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return api_response(message="操作票草稿已创建", data=_ticket_to_response(t))


@router.get("/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    t = db.query(OperationTicket).filter(OperationTicket.id == ticket_id).first()
    if not t:
        raise HTTPException(404, "操作票不存在")
    return api_response(data=_ticket_to_response(t))


@router.put("/{ticket_id}")
def update_ticket(
    ticket_id: int,
    payload: OperationTicketUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    t = db.query(OperationTicket).filter(OperationTicket.id == ticket_id).first()
    if not t:
        raise HTTPException(404, "操作票不存在")
    if t.status != OperationTicketStatus.DRAFT:
        raise HTTPException(400, "仅草稿状态可编辑")
    data = payload.model_dump(exclude_unset=True)
    if "steps" in data:
        steps = data.pop("steps")
        t.steps = json.dumps(steps, ensure_ascii=False, default=str)
    for k, v in data.items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return api_response(message="已更新", data=_ticket_to_response(t))


@router.post("/{ticket_id}/submit")
def submit_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    t = _require_status(db, ticket_id, OperationTicketStatus.DRAFT, "仅草稿可提交审核")
    t.status = OperationTicketStatus.PENDING_REVIEW
    db.commit()
    db.refresh(t)
    return api_response(message="已提交审核", data=_ticket_to_response(t))


@router.post("/{ticket_id}/review")
def review_ticket(
    ticket_id: int,
    payload: OperationTicketReview,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.SAFETY_OFFICER)),
):
    """审核：待审核 → 待执行 / 退回草稿"""
    t = _require_status(db, ticket_id, OperationTicketStatus.PENDING_REVIEW, "仅待审核状态可审核")
    t.reviewer = payload.reviewer
    t.reviewed_at = datetime.utcnow()
    t.review_notes = payload.review_notes
    t.status = OperationTicketStatus.READY if payload.approved else OperationTicketStatus.DRAFT
    db.commit()
    db.refresh(t)
    return api_response(
        message="审核通过，可执行" if payload.approved else "审核退回草稿",
        data=_ticket_to_response(t),
    )


@router.post("/{ticket_id}/start")
def start_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    """开始执行：待执行 → 执行中"""
    t = _require_status(db, ticket_id, OperationTicketStatus.READY, "仅待执行状态可开始")
    t.started_at = datetime.utcnow()
    t.status = OperationTicketStatus.EXECUTING
    db.commit()
    db.refresh(t)
    return api_response(message="开始执行", data=_ticket_to_response(t))


@router.post("/{ticket_id}/check-step")
def check_step(
    ticket_id: int,
    payload: OperationStepCheck,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    """勾对单步：仅执行中可勾对"""
    t = _require_status(db, ticket_id, OperationTicketStatus.EXECUTING, "仅执行中可勾对步骤")
    steps = json.loads(t.steps) if t.steps else []
    target = next((s for s in steps if s.get("step") == payload.step), None)
    if not target:
        raise HTTPException(404, f"步骤 {payload.step} 不存在")
    target["done"] = True
    target["checked_at"] = datetime.utcnow().isoformat()
    if payload.notes:
        target["notes"] = payload.notes
    t.steps = json.dumps(steps, ensure_ascii=False)
    db.commit()
    db.refresh(t)
    return api_response(message=f"步骤 {payload.step} 已勾对", data=_ticket_to_response(t))


@router.post("/{ticket_id}/complete")
def complete_ticket(
    ticket_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    """完成：执行中 → 已完成（必须所有步骤已勾对）"""
    t = _require_status(db, ticket_id, OperationTicketStatus.EXECUTING, "仅执行中可完成")
    steps = json.loads(t.steps) if t.steps else []
    pending = [s for s in steps if not s.get("done")]
    if pending:
        raise HTTPException(400, f"仍有 {len(pending)} 步未勾对，不能完成")
    t.completed_at = datetime.utcnow()
    t.status = OperationTicketStatus.COMPLETED
    db.commit()
    db.refresh(t)
    background_tasks.add_task(
        push, "operation_ticket.completed", "操作票已完成",
        f"{t.ticket_code} {t.title}", {"id": t.id},
    )
    return api_response(message="操作票已完成", data=_ticket_to_response(t))


@router.post("/{ticket_id}/cancel")
def cancel_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.SAFETY_OFFICER)),
):
    t = db.query(OperationTicket).filter(OperationTicket.id == ticket_id).first()
    if not t:
        raise HTTPException(404, "操作票不存在")
    if t.status in (OperationTicketStatus.COMPLETED, OperationTicketStatus.CANCELLED):
        raise HTTPException(400, "已完成或已作废，不可再作废")
    t.status = OperationTicketStatus.CANCELLED
    db.commit()
    db.refresh(t)
    return api_response(message="操作票已作废", data=_ticket_to_response(t))


def _require_status(db: Session, ticket_id: int, expected: OperationTicketStatus, msg: str) -> OperationTicket:
    t = db.query(OperationTicket).filter(OperationTicket.id == ticket_id).first()
    if not t:
        raise HTTPException(404, "操作票不存在")
    if t.status != expected:
        raise HTTPException(400, msg)
    return t
