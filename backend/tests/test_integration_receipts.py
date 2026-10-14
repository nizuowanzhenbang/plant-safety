"""真实 SQLite/PostgreSQL 接收：自然键、内容、原子性及历史映射。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os
from threading import Barrier, Lock
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api import integration
from app.api.deps import get_db
from app.config import settings
from app.database import Base
from app.models.hazard import Hazard, HazardStatus
from app.main import app as registered_app


@pytest.fixture(params=['sqlite', 'postgresql'])
def receiver_ctx(request, tmp_path, monkeypatch):
    admin = None
    if request.param == 'postgresql':
        url = os.environ.get('TEST_SAFETY_POSTGRESQL_URL')
        if not url:
            pytest.skip('Set TEST_SAFETY_POSTGRESQL_URL for real receiver PostgreSQL')
        schema = 'safety_test_'+uuid4().hex
        admin = create_engine(url)
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
        engine = create_engine(url, connect_args={'options': '-csearch_path='+schema+' -clock_timeout=5000'})
    else:
        engine = create_engine(f'sqlite:///{tmp_path / "receiver.db"}', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(settings, 'INTEGRATION_SECRET', 'receiver-test-shared-key')
    instance = FastAPI()
    instance.include_router(integration.router)
    def sessions():
        with factory() as db:
            yield db
    instance.dependency_overrides[get_db] = sessions
    client = TestClient(instance, raise_server_exceptions=False, headers={'X-Integration-Secret': 'receiver-test-shared-key'})
    try:
        yield SimpleNamespace(factory=factory, engine=engine, app=instance, client=client)
    finally:
        client.close()
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
            admin.dispose()


def payload(**fields):
    return {'source_system': 'equipment-inspection', 'external_no': 'DF-TEST-001',
            'title': '锅炉测点异常', 'description': '原始点检记录', 'severity': 'CRITICAL',
            'equipment_code': 'EQ-BL-001', 'equipment_name': '测试锅炉',
            'reported_by': '测试人员', 'reported_at': '2026-10-12T12:00:00Z', **fields}


def receive(ctx, **fields):
    return ctx.client.post('/api/integration/hazards', json=payload(**fields))


def state(ctx):
    with ctx.engine.connect() as conn:
        return {table.name: [tuple(row) for row in conn.execute(select(table).order_by(*table.primary_key))]
                for table in Base.metadata.sorted_tables}


def test_ack_has_identity_and_same_event_replays_after_human_edit(receiver_ctx):
    ctx = receiver_ctx
    first = receive(ctx)
    assert first.status_code == 200, first.text
    ack = first.json()['data']
    assert ack['source_system'] == 'equipment-inspection' and ack['external_no'] == 'DF-TEST-001'
    assert type(ack['id']) is int and ack['id'] > 0
    with ctx.factory() as db:
        h = db.get(Hazard, ack['id'])
        h.title = '安全人员修改标题'
        h.status = HazardStatus.VERIFIED
        db.commit()
    before = state(ctx)
    repeated = receive(ctx)
    assert repeated.status_code == 200 and repeated.json()['data']['id'] == ack['id']
    assert repeated.json()['data']['duplicated'] is True
    assert state(ctx) == before
    assert 'integration_receipts' in inspect(ctx.engine).get_table_names()


@pytest.mark.parametrize('change', [{'description': '别的事件内容'}, {'severity': 'MINOR'},
                                   {'reported_at': '2026-11-12T12:00:00Z'}, {'location': '变更位置'},
                                   {'sla_deadline': '2026-12-01T12:00:00Z'}])
def test_same_key_different_content_is_atomic_conflict(receiver_ctx, change):
    ctx = receiver_ctx
    assert receive(ctx).status_code == 200
    before = state(ctx)
    response = receive(ctx, **change)
    assert response.status_code == 409, response.text
    assert state(ctx) == before


def test_equivalent_time_and_null_description_are_same_event(receiver_ctx):
    ctx = receiver_ctx
    first = receive(ctx, description=None)
    assert first.status_code == 200
    response = receive(ctx, description='', severity='critical', reported_at='2026-10-12T20:00:00+08:00')
    assert response.status_code == 200, response.text
    assert response.json()['data']['id'] == first.json()['data']['id']
    assert response.json()['data']['duplicated'] is True


@pytest.mark.parametrize('field,value', [('source_system', ''), ('external_no', '  '),
                                      ('source_system', 'x'*51), ('external_no', 'x'*51),
                                      ('severity', 'unknown'), ('title', ''), ('reported_by', 'x'*51)])
def test_bad_contract_has_422_and_no_writes(receiver_ctx, field, value):
    ctx = receiver_ctx
    before = state(ctx)
    response = receive(ctx, **{field: value})
    assert response.status_code == 422, response.text
    assert state(ctx) == before


def test_raw_nonfinite_date_has_serializable_error(receiver_ctx):
    ctx = receiver_ctx
    before = state(ctx)
    body = payload()
    body['reported_at'] = 'RAW_OVERFLOW'
    response = ctx.client.post('/api/integration/hazards', content=
                               __import__('json').dumps(body).replace('"RAW_OVERFLOW"', '1e309'),
                               headers={'Content-Type': 'application/json'})
    assert response.status_code == 422, response.text
    assert state(ctx) == before


@contextmanager
def overlapping_missing_keys(engine):
    barrier, mutex, seen = Barrier(2), Lock(), set()
    def after(conn, cursor, statement, parameters, context, many):
        sql = ' '.join(statement.lower().split())
        if not sql.startswith('select') or 'hazards.external_source =' not in sql:
            return
        with mutex:
            if conn in seen or len(seen) >= 2:
                return
            seen.add(conn)
        barrier.wait(timeout=5)
    event.listen(engine, 'after_cursor_execute', after)
    try:
        yield
    finally:
        event.remove(engine, 'after_cursor_execute', after)


@pytest.mark.parametrize('same_key', [True, False])
def test_two_overlapping_requests_have_atomic_natural_key_and_numbers(receiver_ctx, same_key):
    ctx = receiver_ctx
    start = Barrier(2)
    def send(key):
        client = TestClient(ctx.app, headers={'X-Integration-Secret': 'receiver-test-shared-key'}, raise_server_exceptions=False)
        try:
            start.wait(timeout=5)
            return client.post('/api/integration/hazards', json=payload(external_no=key))
        finally:
            client.close()
    keys = ['DF-TEST-001', 'DF-TEST-001' if same_key else 'DF-TEST-002']
    with overlapping_missing_keys(ctx.engine), ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, keys))
    assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
    expected = 1 if same_key else 2
    assert len({r.json()['data']['id'] for r in responses}) == expected
    with ctx.factory() as db:
        assert db.query(Hazard).count() == expected


def remove_receipt_to_represent_legacy(ctx):
    if 'integration_receipts' in Base.metadata.tables:
        with ctx.engine.begin() as conn:
            conn.execute(Base.metadata.tables['integration_receipts'].delete())


@pytest.mark.parametrize('conflict', [False, True])
def test_existing_legacy_mapping_is_adopted_only_if_projection_matches(receiver_ctx, conflict):
    ctx = receiver_ctx
    first = receive(ctx)
    assert first.status_code == 200
    remove_receipt_to_represent_legacy(ctx)
    if conflict:
        with ctx.factory() as db:
            db.get(Hazard, first.json()['data']['id']).title = '不同历史内容'
            db.commit()
    before = state(ctx)
    response = receive(ctx)
    assert response.status_code == (409 if conflict else 200), response.text
    if conflict:
        assert state(ctx) == before
    else:
        assert response.json()['data']['id'] == first.json()['data']['id']
        with ctx.engine.connect() as conn:
            table = Base.metadata.tables.get('integration_receipts')
            assert table is not None and len(conn.execute(select(table)).all()) == 1


def test_duplicate_legacy_rows_are_not_arbitrarily_selected(receiver_ctx):
    ctx = receiver_ctx
    first = receive(ctx)
    assert first.status_code == 200
    remove_receipt_to_represent_legacy(ctx)
    with ctx.factory() as db:
        original = db.get(Hazard, first.json()['data']['id'])
        values = {column.name: getattr(original, column.name) for column in Hazard.__table__.columns
                  if column.name not in ['id', 'hazard_code']}
        db.add(Hazard(hazard_code='YH-LEGACY-DUPLICATE', **values))
        db.commit()
    before = state(ctx)
    response = receive(ctx)
    assert response.status_code == 409, response.text
    assert state(ctx) == before


def test_lookup_exposes_identity_for_arbitrary_query_encoded_keys(receiver_ctx):
    ctx = receiver_ctx
    first = receive(ctx, source_system='设备系统', external_no='DF/A:1')
    assert first.status_code == 200
    response = ctx.client.get('/api/integration/hazards/by-external',
                              params={'source_system': '设备系统', 'external_no': 'DF/A:1'})
    assert response.status_code == 200, response.text
    assert response.json()['data']['id'] == first.json()['data']['id']
    assert response.json()['data']['external_no'] == 'DF/A:1'


def test_receipt_storage_failure_rolls_back_hazard_and_receipt(receiver_ctx):
    ctx = receiver_ctx
    before = state(ctx)
    def fail_receipt(conn, cursor, statement, parameters, context, many):
        if statement.lower().startswith('insert into integration_receipts'):
            conn.exec_driver_sql('SELECT * FROM intentional_missing_receiver_receipt_table')
    event.listen(ctx.engine, 'before_cursor_execute', fail_receipt)
    try:
        response = receive(ctx)
        assert response.status_code == 503, response.text
    finally:
        event.remove(ctx.engine, 'before_cursor_execute', fail_receipt)
    assert state(ctx) == before


def test_replay_with_missing_hazard_reference_is_conflict(receiver_ctx):
    ctx = receiver_ctx
    first = receive(ctx)
    assert first.status_code == 200
    # 在未强制 FK 的 SQLite 中模拟旧文件/人工处理造成的孤立映射。
    if ctx.engine.dialect.name != 'sqlite':
        pytest.skip('PostgreSQL foreign key prevents this corruption')
    with ctx.factory() as db:
        db.delete(db.get(Hazard, first.json()['data']['id']))
        db.commit()
    before = state(ctx)
    response = receive(ctx)
    assert response.status_code == 409, response.text
    assert state(ctx) == before


@pytest.mark.parametrize('origin', ['manual', 'safety-check'])
def test_rolled_back_identity_then_receives_keep_other_creation_paths_working(receiver_ctx, origin):
    from app.api import hazards, safety_checks
    from app.api.deps import create_access_token
    from app.models.user import User, UserRole
    from tests.test_check_hazard_ownership import started_record, submit, convert
    ctx = receiver_ctx
    ctx.app.include_router(hazards.router)
    ctx.app.include_router(safety_checks.router)
    with ctx.factory() as db:
        for role in (UserRole.SAFETY_OFFICER, UserRole.OPERATOR):
            db.add(User(username=role.value, role=role, hashed_password='unused', is_active=True))
        db.commit()
    headers = {role.value: {'Authorization': 'Bearer '+create_access_token(role.value)}
               for role in (UserRole.SAFETY_OFFICER, UserRole.OPERATOR)}
    ctx.client.headers.update(headers['OPERATOR'])
    assert receive(ctx).status_code == 200
    # PostgreSQL INSERT 回滚消耗序列值，真实编号竞争也会产生相同 ID 空洞。
    with ctx.factory() as db:
        original = db.query(Hazard).first()
        values = {column.name: getattr(original, column.name) for column in Hazard.__table__.columns
                  if column.name != 'id'}
        values.update(hazard_code='ROLLED-BACK', external_no='ROLLED-BACK')
        db.add(Hazard(**values))
        db.flush()
        db.rollback()
    assert receive(ctx, external_no='SECOND').status_code == 200
    assert receive(ctx, external_no='THIRD').status_code == 200
    if origin == 'manual':
        response = ctx.client.post('/api/hazards', json={
            'title': '正常人工登记', 'description': '编号竞争后应仍可登记', 'area': 'MAIN_PLANT',
            'category': 'MECHANICAL', 'level': 'GENERAL', 'reporter': '测试人员'})
    else:
        api = (ctx.client, ctx.factory, headers)
        record_id = started_record(api)
        assert submit(ctx.client, record_id).status_code == 200
        response = convert(ctx.client, record_id)
    assert response.status_code == 200, response.text
    with ctx.factory() as db:
        codes = [h.hazard_code for h in db.query(Hazard)]
        assert len(codes) == len(set(codes)) == 4



def test_startup_adds_number_state_preserves_legacy_data_and_does_not_reuse_deletions(receiver_ctx):
    from app.models.integration_receipt import IntegrationReceipt
    ctx = receiver_ctx
    assert receive(ctx).status_code == 200
    with ctx.factory() as db:
        old = db.query(Hazard).first()
        prefix = old.hazard_code.rsplit('-', 1)[0]+'-'
        values = {column.name: getattr(old, column.name) for column in Hazard.__table__.columns
                  if column.name != 'id'}
        values.update(hazard_code=prefix+'9000', external_no='LEGACY-9000')
        db.add(Hazard(**values))
        db.commit()
    Base.metadata.tables['integration_receipts'].drop(ctx.engine)
    Base.metadata.tables['hazard_number_sequences'].drop(ctx.engine)
    with ctx.engine.connect() as conn:
        before = [tuple(row) for row in conn.execute(select(Hazard.__table__).order_by(Hazard.id))]
    Base.metadata.create_all(ctx.engine)
    Base.metadata.create_all(ctx.engine)
    with ctx.engine.connect() as conn:
        assert [tuple(row) for row in conn.execute(select(Hazard.__table__).order_by(Hazard.id))] == before
    first = receive(ctx, external_no='NEW-9001')
    assert first.status_code == 200, first.text
    assert first.json()['data']['hazard_no'] == prefix+'9001'
    did = first.json()['data']['id']
    with ctx.factory() as db:
        db.query(IntegrationReceipt).filter_by(hazard_id=did).delete()
        db.delete(db.get(Hazard, did))
        db.commit()
    second = receive(ctx, external_no='NEW-9002')
    assert second.status_code == 200, second.text
    assert second.json()['data']['hazard_no'] == prefix+'9002'
