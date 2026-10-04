"""通过真实路由、JWT 和临时数据库验证检查结果的隐患关联归属。"""
import json
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import hazards, safety_checks
from app.api.deps import create_access_token, get_db
from app.config import settings
from app.database import Base
from app.models.hazard import Hazard
from app.models.safety_check import SafetyCheckRecord
from app.models.user import User, UserRole


@pytest.fixture
def api(monkeypatch):
    """仅替换数据库连接和测试密钥，保留真实鉴权与业务代码。"""
    monkeypatch.setattr(settings, "SECRET_KEY", "check-ownership-test-key")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    with factory() as db:
        for role in (UserRole.SAFETY_OFFICER, UserRole.OPERATOR, UserRole.VIEWER):
            db.add(User(username=role.value, role=role, hashed_password="unused", is_active=True))
        db.commit()

    def test_db():
        with factory() as db:
            yield db

    app = FastAPI()
    app.include_router(safety_checks.router)
    app.include_router(hazards.router)
    app.dependency_overrides[get_db] = test_db
    headers = {
        role.value: {"Authorization": "Bearer " + create_access_token(role.value)}
        for role in (UserRole.SAFETY_OFFICER, UserRole.OPERATOR, UserRole.VIEWER)
    }
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            client.headers.update(headers["OPERATOR"])
            yield client, factory, headers
    finally:
        engine.dispose()


def started_record(api):
    client, _, headers = api
    response = client.post("/api/safety-checks/plans", headers=headers["SAFETY_OFFICER"], json={
        "name": "锅炉辅机防护检查", "area": "BOILER", "frequency": "DAILY",
        "owner_dept": "运行班组", "item_template": [
            {"seq": 1, "content": "联轴器防护罩完整", "standard": "防护罩无缺损"},
            {"seq": 2, "content": "通道畅通"},
        ],
    })
    assert response.status_code == 200, response.text
    response = client.post("/api/safety-checks/records/generate", headers=headers["SAFETY_OFFICER"], json={
        "plan_id": response.json()["data"]["id"], "scheduled_dates": [date.today().isoformat()],
    })
    assert response.status_code == 200, response.text
    record_id = response.json()["data"][0]["id"]
    response = client.post(f"/api/safety-checks/records/{record_id}/start", json={"inspector": "测试检查员"})
    assert response.status_code == 200, response.text
    return record_id


def submission():
    return {"inspector": "测试检查员", "summary": "防护罩缺损需整改", "result_items": [
        {"seq": 1, "content": "联轴器防护罩完整", "standard": "防护罩无缺损",
         "conformant": False, "notes": "模拟缺损"},
        {"seq": 2, "content": "通道畅通", "conformant": True},
    ]}


def submit(client, record_id, payload=None):
    return client.post(f"/api/safety-checks/records/{record_id}/submit", json=payload or submission())


def convert(client, record_id, seq=1):
    return client.post(f"/api/safety-checks/records/{record_id}/convert-hazard", json={
        "seq": seq, "category": "MECHANICAL", "level": "GENERAL",
    })


def state(factory):
    """比较全部持久化字段，拒绝请求不能偷偷改变状态、时间或关联。"""
    with factory() as db:
        return {
            model.__tablename__: [
                {column.name: getattr(row, column.name) for column in model.__table__.columns}
                for row in db.query(model).order_by(model.id).all()
            ]
            for model in (SafetyCheckRecord, Hazard)
        }


@pytest.mark.parametrize("forged_id", [999999, 0, -1, "999999", True])
def test_client_cannot_supply_hazard_id(api, forged_id):
    client, factory, _ = api
    record_id = started_record(api)
    before = state(factory)
    payload = submission()
    payload["result_items"][0]["hazard_id"] = forged_id
    response = submit(client, record_id, payload)
    assert response.status_code == 422, response.text
    assert any(e["loc"] == ["body", "result_items", 0, "hazard_id"] for e in response.json()["detail"])
    assert state(factory) == before
    assert submit(client, record_id).status_code == 200
    assert convert(client, record_id).status_code == 200
    with factory() as db:
        assert db.query(Hazard).count() == 1


def test_invalid_link_on_conformant_item_rejects_entire_submission(api):
    client, factory, _ = api
    record_id = started_record(api)
    before = state(factory)
    payload = submission()
    payload["result_items"][1]["hazard_id"] = 999999
    assert submit(client, record_id, payload).status_code == 422
    assert state(factory) == before


@pytest.mark.parametrize("explicit_null", [False, True])
def test_server_creates_link_and_repeated_conversion_keeps_original(api, explicit_null):
    client, factory, _ = api
    record_id = started_record(api)
    payload = submission()
    if explicit_null:
        for item in payload["result_items"]:
            item["hazard_id"] = None
    response = submit(client, record_id, payload)
    assert response.status_code == 200, response.text
    record = response.json()["data"]
    assert record["status"] == "COMPLETED"
    assert record["total_items"] == 2 and record["nonconformant_count"] == 1
    assert all(item["hazard_id"] is None for item in record["result_items"])
    response = convert(client, record_id)
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    hazard_id = result["hazard_id"]
    assert result["record"]["result_items"][0]["hazard_id"] == hazard_id
    assert result["record"]["result_items"][1]["hazard_id"] is None
    response = client.get(f"/api/hazards/{hazard_id}")
    assert response.status_code == 200, response.text
    detail = response.json()["data"]
    assert detail["reporter"] == "测试检查员" and detail["area"] == "BOILER"
    assert "模拟缺损" in detail["description"]
    with factory() as db:
        assert db.query(Hazard).count() == 1
        hazard = db.get(Hazard, hazard_id)
        assert hazard.external_source == "safety-check"
        assert hazard.external_no == record["record_code"] + "-1"
        assert json.loads(db.get(SafetyCheckRecord, record_id).result_items)[0]["hazard_id"] == hazard_id
    before = state(factory)
    assert convert(client, record_id).status_code == 400
    assert convert(client, record_id, seq=2).status_code == 400
    assert state(factory) == before
    assert client.get(f"/api/safety-checks/records/{record_id}").json()["data"] == result["record"]


def test_existing_hazard_from_another_record_cannot_be_attached(api):
    client, factory, _ = api
    first = started_record(api)
    assert submit(client, first).status_code == 200
    hazard_id = convert(client, first).json()["data"]["hazard_id"]
    second = started_record(api)
    before = state(factory)
    payload = submission()
    payload["result_items"][0]["hazard_id"] = hazard_id
    assert submit(client, second, payload).status_code == 422
    assert state(factory) == before


def test_completed_record_cannot_be_resubmitted_or_restarted(api):
    client, factory, _ = api
    record_id = started_record(api)
    assert submit(client, record_id).status_code == 200
    assert convert(client, record_id).status_code == 200
    before = state(factory)
    assert submit(client, record_id).status_code == 400
    assert client.post(f"/api/safety-checks/records/{record_id}/start", json={"inspector": "其他人"}).status_code == 400
    assert state(factory) == before


@pytest.mark.parametrize("actor, expected", [("VIEWER", 403), (None, 401)])
def test_unauthorized_submit_and_convert_leave_database_unchanged(api, actor, expected):
    client, factory, headers = api
    record_id = started_record(api)
    before = state(factory)
    client.headers.pop("Authorization")
    if actor:
        client.headers.update(headers[actor])
    assert submit(client, record_id).status_code == expected
    assert state(factory) == before
    client.headers.update(headers["OPERATOR"])
    assert submit(client, record_id).status_code == 200
    before = state(factory)
    client.headers.pop("Authorization")
    if actor:
        client.headers.update(headers[actor])
    assert convert(client, record_id).status_code == expected
    assert state(factory) == before


def test_conversion_write_failure_rolls_back_hazard_and_link(api):
    client, factory, _ = api
    record_id = started_record(api)
    assert submit(client, record_id).status_code == 200
    before = state(factory)
    with factory() as db:
        db.execute(text("""CREATE TRIGGER reject_link_update
            BEFORE UPDATE OF result_items ON safety_check_records
            BEGIN SELECT RAISE(ABORT, 'injected link write failure'); END"""))
        db.commit()
    assert convert(client, record_id).status_code == 500
    assert state(factory) == before
    with factory() as db:
        db.execute(text("DROP TRIGGER reject_link_update"))
        db.commit()
    assert convert(client, record_id).status_code == 200
    with factory() as db:
        assert db.query(Hazard).count() == 1
