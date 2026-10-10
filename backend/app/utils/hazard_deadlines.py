"""隐患期限按发现时刻和有效等级统一校验，数据库继续存 UTC naive。"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.models.hazard import HazardLevel


def max_deadline_days(level: HazardLevel) -> int:
    return 14 if level == HazardLevel.MAJOR else 30


def normalize_utc(value: datetime) -> datetime:
    """带偏移的输入换算为 UTC；既有无时区时间按 UTC 解释。"""
    try:
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    except (OverflowError, ValueError) as error:
        raise HTTPException(422, "发现时间或整改期限超出可处理范围") from error


def deadline_for(
    level: HazardLevel, reported_at: datetime, deadline: datetime | None = None,
) -> datetime:
    """缺省补等级期限；只限制上限，保留过去期限和历史超期识别。"""
    days = max_deadline_days(level)
    try:
        limit = normalize_utc(reported_at) + timedelta(days=days)
    except OverflowError as error:
        raise HTTPException(422, "发现时间无法生成有效整改期限") from error
    value = normalize_utc(deadline) if deadline is not None else limit
    if value > limit:
        label = "重大" if level == HazardLevel.MAJOR else "一般"
        raise HTTPException(422, f"{label}隐患整改期限不得超过发现时间后 {days} 天，请调整期限")
    return value
