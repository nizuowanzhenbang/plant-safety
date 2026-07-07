"""安全检查 API：计划 + 记录 + 不符合项转隐患"""
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_min_role
from app.api.ws import push
from app.models.safety_check import (
    SafetyCheckPlan, SafetyCheckRecord,
    CheckFrequency, CheckPlanStatus, CheckRecordStatus,
)
from app.models.hazard import Hazard, HazardArea, HazardLevel, HazardStatus
from app.models.user import User, UserRole
from app.schemas.safety_check import (
    CheckItemTemplate, CheckResultItem,
    SafetyCheckPlanCreate, SafetyCheckPlanUpdate, SafetyCheckPlanResponse,
    GenerateRecordsRequest, StartCheckRequest, SubmitCheckRequest,
    ConvertHazardRequest, SafetyCheckRecordResponse,
)
from app.utils.helpers import (
    api_response, paginate_response, generate_safety_check_code, generate_hazard_code,
)

router = APIRouter(prefix="/api/safety-checks", tags=["安全检查"])


# ============== 检查计划 ==============

def _plan_to_response(p: SafetyCheckPlan) -> dict:
    return {
        "id": p.id, "name": p.name, "area": p.area, "frequency": p.frequency,
        "owner_dept": p.owner_dept, "description": p.description,
        "item_template": json.loads(p.item_template) if p.item_template else [],
        "status": p.status, "created_at": p.created_at, "updated_at": p.updated_at,
    }


@router.get("/plans")
def list_plans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    area: Optional[HazardArea] = None,
    frequency: Optional[CheckFrequency] = None,
    status: Optional[CheckPlanStatus] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(SafetyCheckPlan)
    if area:
        q = q.filter(SafetyCheckPlan.area == area.value)
    if frequency:
        q = q.filter(SafetyCheckPlan.frequency == frequency)
    if status:
        q = q.filter(SafetyCheckPlan.status == status)
    total = q.count()
    rows = q.order_by(SafetyCheckPlan.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [_plan_to_response(r) for r in rows]
    return api_response(data=paginate_response(items, total, page, page_size))


@router.post("/plans")
def create_plan(
    payload: SafetyCheckPlanCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.SAFETY_OFFICER)),
):
    if not payload.item_template:
        raise HTTPException(400, "检查项模板不能为空")
    p = SafetyCheckPlan(
        name=payload.name,
        area=payload.area.value,
        frequency=payload.frequency,
        owner_dept=payload.owner_dept,
        description=payload.description,
        item_template=json.dumps(
            [i.model_dump() for i in payload.item_template], ensure_ascii=False,
        ),
        status=CheckPlanStatus.ACTIVE,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return api_response(message="检查计划已创建", data=_plan_to_response(p))


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    p = db.query(SafetyCheckPlan).filter(SafetyCheckPlan.id == plan_id).first()
    if not p:
        raise HTTPException(404, "计划不存在")
    return api_response(data=_plan_to_response(p))


@router.put("/plans/{plan_id}")
def update_plan(
    plan_id: int,
    payload: SafetyCheckPlanUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.SAFETY_OFFICER)),
):
    p = db.query(SafetyCheckPlan).filter(SafetyCheckPlan.id == plan_id).first()
    if not p:
        raise HTTPException(404, "计划不存在")
    data = payload.model_dump(exclude_unset=True)
    if "area" in data and data["area"]:
        data["area"] = data["area"].value if hasattr(data["area"], "value") else data["area"]
    if "item_template" in data and data["item_template"]:
        items = data.pop("item_template")
        p.item_template = json.dumps(
            [i if isinstance(i, dict) else i.model_dump() for i in items],
            ensure_ascii=False,
        )
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return api_response(message="已更新", data=_plan_to_response(p))


# ============== 检查记录 ==============

def _record_to_response(r: SafetyCheckRecord) -> dict:
    plan_name = r.plan.name if r.plan else None
    plan_area = r.plan.area if r.plan else None
    return {
        "id": r.id, "record_code": r.record_code, "plan_id": r.plan_id,
        "plan_name": plan_name,
        "area": plan_area,
        "scheduled_date": r.scheduled_date,
        "inspector": r.inspector,
        "started_at": r.started_at, "completed_at": r.completed_at,
        "result_items": json.loads(r.result_items) if r.result_items else [],
        "total_items": r.total_items, "nonconformant_count": r.nonconformant_count,
        "summary": r.summary, "status": r.status,
        "created_at": r.created_at, "updated_at": r.updated_at,
    }


@router.post("/records/generate")
def generate_records(
    payload: GenerateRecordsRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.SAFETY_OFFICER)),
):
    """从某计划批量生成检查记录（PENDING）"""
    plan = db.query(SafetyCheckPlan).filter(SafetyCheckPlan.id == payload.plan_id).first()
    if not plan:
        raise HTTPException(404, "计划不存在")
    if plan.status != CheckPlanStatus.ACTIVE:
        raise HTTPException(400, "仅启用的计划可生成记录")

    template = json.loads(plan.item_template) if plan.item_template else []
    total_items = len(template)

    created = []
    seq_base = (db.query(func.count(SafetyCheckRecord.id)).scalar() or 0)
    for idx, d in enumerate(payload.scheduled_dates, 1):
        rec = SafetyCheckRecord(
            record_code=generate_safety_check_code(seq_base + idx),
            plan_id=plan.id,
            scheduled_date=d,
            total_items=total_items,
            nonconformant_count=0,
            status=CheckRecordStatus.PENDING,
        )
        db.add(rec)
        created.append(rec)
    db.commit()
    for r in created:
        db.refresh(r)
    return api_response(
        message=f"已生成 {len(created)} 条检查记录",
        data=[_record_to_response(r) for r in created],
    )


@router.get("/records")
def list_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    plan_id: Optional[int] = None,
    status: Optional[CheckRecordStatus] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(SafetyCheckRecord)
    if plan_id:
        q = q.filter(SafetyCheckRecord.plan_id == plan_id)
    if status:
        q = q.filter(SafetyCheckRecord.status == status)

    # 自动标记超期：scheduled_date < 今天且仍 PENDING
    today = datetime.utcnow().date()
    overdue_rows = db.query(SafetyCheckRecord).filter(
        SafetyCheckRecord.scheduled_date < today,
        SafetyCheckRecord.status == CheckRecordStatus.PENDING,
    ).all()
    if overdue_rows:
        for r in overdue_rows:
            r.status = CheckRecordStatus.OVERDUE
        db.commit()

    total = q.count()
    rows = q.order_by(SafetyCheckRecord.scheduled_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [_record_to_response(r) for r in rows]
    return api_response(data=paginate_response(items, total, page, page_size))


@router.get("/records/{record_id}")
def get_record(record_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    r = db.query(SafetyCheckRecord).filter(SafetyCheckRecord.id == record_id).first()
    if not r:
        raise HTTPException(404, "记录不存在")
    return api_response(data=_record_to_response(r))


@router.post("/records/{record_id}/start")
def start_record(
    record_id: int,
    payload: StartCheckRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    r = db.query(SafetyCheckRecord).filter(SafetyCheckRecord.id == record_id).first()
    if not r:
        raise HTTPException(404, "记录不存在")
    if r.status not in (CheckRecordStatus.PENDING, CheckRecordStatus.OVERDUE):
        raise HTTPException(400, "仅 待执行/超期 状态可开始检查")
    r.inspector = payload.inspector
    r.started_at = datetime.utcnow()
    r.status = CheckRecordStatus.IN_PROGRESS
    db.commit()
    db.refresh(r)
    return api_response(message="开始检查", data=_record_to_response(r))


@router.post("/records/{record_id}/submit")
def submit_record(
    record_id: int,
    payload: SubmitCheckRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    """提交检查结果：检查中 → 已完成"""
    r = db.query(SafetyCheckRecord).filter(SafetyCheckRecord.id == record_id).first()
    if not r:
        raise HTTPException(404, "记录不存在")
    if r.status != CheckRecordStatus.IN_PROGRESS:
        raise HTTPException(400, "仅检查中状态可提交")

    nonconformant = sum(1 for it in payload.result_items if not it.conformant)
    r.inspector = payload.inspector
    r.result_items = json.dumps(
        [it.model_dump() for it in payload.result_items], ensure_ascii=False,
    )
    r.total_items = len(payload.result_items)
    r.nonconformant_count = nonconformant
    r.summary = payload.summary
    r.completed_at = datetime.utcnow()
    r.status = CheckRecordStatus.COMPLETED
    db.commit()
    db.refresh(r)
    if nonconformant > 0:
        background_tasks.add_task(
            push, "safety_check.nonconformant", "安全检查发现不符合项",
            f"{r.record_code} 发现 {nonconformant} 项不符合，待整改",
            {"record_id": r.id, "nonconformant": nonconformant},
        )
    return api_response(
        message=f"检查完成，{nonconformant} 项不符合",
        data=_record_to_response(r),
    )


@router.post("/records/{record_id}/convert-hazard")
def convert_to_hazard(
    record_id: int,
    payload: ConvertHazardRequest,
    db: Session = Depends(get_db),
    current: User = Depends(require_min_role(UserRole.OPERATOR)),
):
    """把已完成检查记录里的某条不符合项转为隐患单"""
    r = db.query(SafetyCheckRecord).filter(SafetyCheckRecord.id == record_id).first()
    if not r:
        raise HTTPException(404, "记录不存在")
    if r.status != CheckRecordStatus.COMPLETED:
        raise HTTPException(400, "仅已完成的检查可转隐患")
    items = json.loads(r.result_items) if r.result_items else []
    target = next((it for it in items if it.get("seq") == payload.seq), None)
    if not target:
        raise HTTPException(404, f"检查项 {payload.seq} 不存在")
    if target.get("conformant"):
        raise HTTPException(400, "该项检查为符合，无需转隐患")
    if target.get("hazard_id"):
        raise HTTPException(400, f"该项已转隐患单 {target['hazard_id']}")

    plan = r.plan
    area_enum = HazardArea(plan.area) if plan else HazardArea.MAIN_PLANT
    deadline_days = payload.deadline_days or (14 if payload.level == HazardLevel.MAJOR else 30)

    seq = (db.query(func.count(Hazard.id)).scalar() or 0) + 1
    title = f"[安全检查] {target.get('content', '')[:160]}"
    description_parts = [
        f"来源：安全检查记录 {r.record_code} 第 {payload.seq} 项",
        f"检查内容：{target.get('content', '')}",
    ]
    if target.get("standard"):
        description_parts.append(f"检查标准：{target['standard']}")
    if target.get("notes"):
        description_parts.append(f"现场说明：{target['notes']}")

    h = Hazard(
        hazard_code=generate_hazard_code(seq),
        title=title[:200],
        description="\n".join(description_parts),
        area=area_enum,
        category=payload.category,
        level=payload.level,
        reporter=r.inspector or current.username,
        department=plan.owner_dept if plan else None,
        reported_at=datetime.utcnow(),
        assignee=payload.assignee,
        assignee_dept=payload.assignee_dept,
        deadline=datetime.utcnow() + timedelta(days=deadline_days),
        external_source="safety-check",
        external_no=f"{r.record_code}-{payload.seq}",
        status=HazardStatus.IN_PROGRESS if payload.assignee else HazardStatus.PENDING,
    )
    db.add(h)
    db.flush()

    target["hazard_id"] = h.id
    r.result_items = json.dumps(items, ensure_ascii=False)
    db.commit()
    db.refresh(h)
    db.refresh(r)
    return api_response(
        message="已生成隐患单",
        data={"hazard_id": h.id, "hazard_code": h.hazard_code, "record": _record_to_response(r)},
    )
