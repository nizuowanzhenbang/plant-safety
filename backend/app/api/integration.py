"""跨系统集成接口：接收 equipment-inspection 推送的 CRITICAL 缺陷，落地为隐患单"""
from datetime import datetime
from typing import Annotated, Literal, Optional
from hashlib import sha256
import json
from math import isfinite

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import func
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.models.integration_receipt import IntegrationReceipt

from app.api.deps import get_db
from app.config import settings
from app.models.hazard import (
    Hazard, HazardArea, HazardCategory, HazardLevel, HazardStatus,
)
from app.utils.helpers import api_response, generate_hazard_code
from app.utils.hazard_deadlines import deadline_for, normalize_utc
from fastapi import Depends

router = APIRouter(prefix="/api/integration", tags=["跨系统集成"])


Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


def safe_json_values(value):
    # 无论坏值在字段/数组何处，422 的错误详情也必须可序列化。
    if isinstance(value, float) and not isfinite(value):
        return {'non_finite': str(value)}
    if isinstance(value, dict):
        return {key: safe_json_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_json_values(item) for item in value]
    return value


class IncomingHazard(BaseModel):
    external_no: Key
    source_system: Key = 'equipment-inspection'
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: Optional[str] = None
    severity: Literal['MINOR', 'MAJOR', 'CRITICAL']
    equipment_code: Optional[Annotated[str, Field(max_length=50)]] = None
    equipment_name: Optional[Annotated[str, Field(max_length=100)]] = None
    location: Optional[Annotated[str, Field(max_length=100)]] = None
    reported_by: Optional[Annotated[str, Field(max_length=50)]] = None
    reported_at: Optional[datetime] = None
    sla_deadline: Optional[datetime] = None
    model_config = ConfigDict(extra='ignore')

    @model_validator(mode='before')
    @classmethod
    def serialize_invalid_values(cls, value):
        return safe_json_values(value)

    @field_validator('severity', mode='before')
    @classmethod
    def normalize_severity(cls, value):
        return value.upper() if isinstance(value, str) else value




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


def normalized_payload(payload):
    result = payload.model_dump(mode='json')
    result['description'] = payload.description or ''
    for name in ['reported_at', 'sla_deadline']:
        value = getattr(payload, name)
        result[name] = normalize_utc(value).isoformat() if value is not None else None
    for name in ['equipment_code', 'equipment_name', 'location', 'reported_by']:
        result[name] = result[name] or None
    return result


def _description(payload):
    parts = [payload.description or payload.title]
    if payload.equipment_code:
        parts += [f'[来源] {payload.source_system} 单号 {payload.external_no}',
                  f"[设备] {payload.equipment_code} {payload.equipment_name or ''}"]
    return '\n'.join(parts)


def _ack(hazard, source, external_no, duplicated):
    if hazard is None or hazard.id <= 0:
        raise HTTPException(409, '联动映射的隐患引用缺失，请核对')
    return api_response(data={'hazard_no': hazard.hazard_code, 'id': hazard.id,
                              'source_system': source, 'external_no': external_no,
                              'duplicated': duplicated})


def _existing_receipt(db, source, external_no):
    return db.query(IntegrationReceipt).filter(IntegrationReceipt.external_source == source,
                                               IntegrationReceipt.external_no == external_no).first()


def _replay(db, receipt, fingerprint):
    if receipt.payload_hash != fingerprint:
        raise HTTPException(409, '同一来源单号已用于不同内容，请核对原消息')
    return _ack(db.get(Hazard, receipt.hazard_id), receipt.external_source, receipt.external_no, True)


def _legacy_matches(hazard, payload):
    expected = {'title': f'[联动] {payload.title}'[:200], 'description': _description(payload),
                'area': _map_area(payload.equipment_code), 'category': HazardCategory.MECHANICAL,
                'level': _map_level(payload.severity), 'reporter': payload.reported_by or 'external-integration',
                'department': payload.source_system}
    if payload.reported_at is not None:
        expected['reported_at'] = normalize_utc(payload.reported_at)
    return all(getattr(hazard, field) == value for field, value in expected.items())


def _next_code(db, clock):
    prefix = f'YH-{clock:%Y%m%d}-'
    codes = db.query(Hazard.hazard_code).filter(Hazard.hazard_code.like(prefix+'%')).all()
    suffix = max((int(code[len(prefix):]) for (code,) in codes
                  if code[len(prefix):].isascii() and code[len(prefix):].isdigit()), default=0)
    sequence = max(suffix, db.query(func.max(Hazard.id)).scalar() or 0)+1
    return f'{prefix}{sequence:04d}'


@router.post('/hazards')
def receive_hazard(payload: IncomingHazard, db: Session = Depends(get_db),
                   x_integration_secret: Optional[str] = Header(None, alias='X-Integration-Secret')):
    """自然键/原消息收据与隐患同事务；冲突不会静默当作重复成功。"""
    _verify_secret(x_integration_secret)
    original = normalized_payload(payload)
    fingerprint = sha256(json.dumps(original, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()
    source, external_no = payload.source_system, payload.external_no
    clock = None
    for _ in range(8):
        receipt = _existing_receipt(db, source, external_no)
        if receipt:
            return _replay(db, receipt, fingerprint)
        existing = db.query(Hazard).filter(Hazard.external_source == source,
                                           Hazard.external_no == external_no).limit(2).all()
        if len(existing) > 1:
            raise HTTPException(409, '历史来源单号有多个隐患，请先核对')
        if existing and not _legacy_matches(existing[0], payload):
            raise HTTPException(409, '历史隐患与消息内容不一致，不能确认重放')
        try:
            if existing:
                hazard = existing[0]
            else:
                if clock is None:
                    clock = datetime.utcnow()
                reported = normalize_utc(payload.reported_at or clock)
                level = _map_level(payload.severity)
                deadline = deadline_for(level, reported)
                hazard = Hazard(hazard_code=_next_code(db, clock), title=f'[联动] {payload.title}'[:200],
                                description=_description(payload), area=_map_area(payload.equipment_code),
                                category=HazardCategory.MECHANICAL, level=level,
                                reporter=payload.reported_by or 'external-integration', department=source,
                                reported_at=reported, deadline=deadline, status=HazardStatus.PENDING,
                                external_source=source, external_no=external_no)
                db.add(hazard)
                db.flush()
            if hazard.id <= 0:
                raise HTTPException(503, '隐患引用无法确认，请核对数据库')
            db.add(IntegrationReceipt(external_source=source, external_no=external_no,
                                      payload_hash=fingerprint, payload=original, hazard_id=hazard.id))
            db.commit()
            return _ack(hazard, source, external_no, bool(existing))
        except IntegrityError:
            # 同自然键或编号竞争，整事务回滚后按最新已提交记录重新判。
            db.rollback()
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(503, '联动未持久确认，请稍后用原消息重试') from None
    raise HTTPException(503, '联动编号或来源竞争，请稍后用原消息重试')


def _lookup(db, source, external_no):
    receipt = _existing_receipt(db, source, external_no)
    if receipt:
        hazard = db.get(Hazard, receipt.hazard_id)
    else:
        rows = db.query(Hazard).filter(Hazard.external_source == source, Hazard.external_no == external_no).limit(2).all()
        if len(rows) > 1:
            raise HTTPException(409, '历史来源单号有多个隐患，请先核对')
        hazard = rows[0] if rows else None
    if hazard is None:
        raise HTTPException(404, '未找到有效联动隐患')
    result = _ack(hazard, source, external_no, True)['data']
    result.update(status=hazard.status.value, deadline=hazard.deadline.isoformat() if hazard.deadline else None,
                  rectified_at=hazard.rectified_at.isoformat() if hazard.rectified_at else None)
    return api_response(data=result)


@router.get('/hazards/by-external')
def lookup_query(source_system: Key, external_no: Key, db: Session = Depends(get_db),
                 x_integration_secret: Optional[str] = Header(None, alias='X-Integration-Secret')):
    """查询参数支持 Unicode 和含斜线单号；旧路径接口继续保留。"""
    _verify_secret(x_integration_secret)
    return _lookup(db, source_system, external_no)


@router.get('/hazards/by-external/{source}/{external_no}')
def lookup_by_external(source: Key, external_no: Key, db: Session = Depends(get_db),
                       x_integration_secret: Optional[str] = Header(None, alias='X-Integration-Secret')):
    _verify_secret(x_integration_secret)
    return _lookup(db, source, external_no)
