"""隐患接收、人工登记、安全检查共用的数据库原子编号。"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.hazard import Hazard, HazardNumberSequence

MAX_SEQUENCE = 2147483647


def allocate_hazard_number(db, clock=None):
    day = (clock or datetime.utcnow()).strftime('%Y%m%d')
    prefix = f'YH-{day}-'
    if db.get(HazardNumberSequence, day) is None:
        codes = db.query(Hazard.hazard_code).filter(Hazard.hazard_code.like(prefix+'%')).all()
        largest = max((int(code[len(prefix):]) for (code,) in codes
                       if code[len(prefix):].isascii() and code[len(prefix):].isdigit()), default=0)
        if largest >= MAX_SEQUENCE:
            raise HTTPException(409, '当日隐患编号已达到上限')
        insert = sqlite_insert if db.get_bind().dialect.name == 'sqlite' else pg_insert
        db.execute(insert(HazardNumberSequence).values(day=day, last_value=largest)
                   .on_conflict_do_nothing(index_elements=['day']))
    value = db.execute(update(HazardNumberSequence)
                       .where(HazardNumberSequence.day == day, HazardNumberSequence.last_value < MAX_SEQUENCE)
                       .values(last_value=HazardNumberSequence.last_value+1)
                       .returning(HazardNumberSequence.last_value)).scalar_one_or_none()
    if value is None:
        raise HTTPException(409, '当日隐患编号已达到上限')
    return f'{prefix}{value:04d}'
