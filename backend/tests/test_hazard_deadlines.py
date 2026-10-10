"""真实 API 和数据库验证期限上限、时间语义及拒绝后的原子性。"""
from datetime import datetime, timedelta, timezone

import pytest

from app.api import dashboard, hazards, integration, safety_checks
from app.config import settings
from app.models.hazard import Hazard, HazardStatus
from test_check_hazard_ownership import api, started_record, state, submit


NOW = datetime(2026, 10, 10, 12, 0)


class FixedClock(datetime):
    @classmethod
    def utcnow(cls):
        return NOW


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    for module in (hazards, safety_checks, integration, dashboard):
        monkeypatch.setattr(module, "datetime", FixedClock)
    monkeypatch.setattr(settings, "INTEGRATION_SECRET", "deadline-integration-test-key")


def payload(level="GENERAL", **extra):
    return {"title": "模拟防护隐患", "description": "演示整改期限",
            "area": "BOILER", "category": "MECHANICAL", "level": level,
            "reporter": "测试人员", **extra}


def create(client, level="GENERAL", **extra):
    response = client.post("/api/hazards", json=payload(level, **extra))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def legacy(factory, hazard_id, **values):
    """构造真实历史行，不绕过本轮待验证的写入口。"""
    with factory() as db:
        row = db.get(Hazard, hazard_id)
        for field, value in values.items():
            setattr(row, field, value)
        db.commit()


@pytest.mark.parametrize("level,days", [("MAJOR", 14), ("GENERAL", 30)])
def test_create_rejects_deadline_over_limit(api, level, days):
    client, factory, _ = api
    before = state(factory)
    response = client.post("/api/hazards", json=payload(
        level, deadline=(NOW + timedelta(days=days, microseconds=1)).isoformat(),
    ))
    assert response.status_code == 422, response.text
    assert state(factory) == before


@pytest.mark.parametrize("level,days", [("MAJOR", 14), ("GENERAL", 30)])
@pytest.mark.parametrize("offset", [8, -5])
def test_create_accepts_exact_limit_in_any_timezone(api, level, days, offset):
    client, factory, _ = api
    limit = NOW + timedelta(days=days)
    encoded = limit.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=offset)))
    data = create(client, level, deadline=encoded.isoformat())
    assert datetime.fromisoformat(data["deadline"]) == limit
    with factory() as db:
        assert db.get(Hazard, data["id"]).deadline == limit


@pytest.mark.parametrize("level,days", [("MAJOR", 14), ("GENERAL", 30)])
@pytest.mark.parametrize("explicit_null", [False, True])
def test_create_defaults_missing_or_null_deadline(api, level, days, explicit_null):
    client, _, _ = api
    data = create(client, level, **({"deadline": None} if explicit_null else {}))
    assert datetime.fromisoformat(data["reported_at"]) == NOW
    assert datetime.fromisoformat(data["deadline"]) == NOW + timedelta(days=days)


def test_past_deadline_remains_compatible_with_overdue_detection(api):
    client, factory, _ = api
    data = create(client, deadline=(NOW - timedelta(days=1)).isoformat())
    client.app.include_router(dashboard.router)
    assert client.get("/api/dashboard/overview").status_code == 200
    with factory() as db:
        assert db.get(Hazard, data["id"]).status == HazardStatus.OVERDUE


@pytest.mark.parametrize("level,days", [("MAJOR", 14), ("GENERAL", 30)])
def test_update_uses_original_reported_at(api, level, days):
    client, factory, _ = api
    row = create(client, level, deadline=(NOW + timedelta(days=1)).isoformat())
    discovered = NOW - timedelta(days=5)
    legacy(factory, row["id"], reported_at=discovered, deadline=discovered + timedelta(days=1))
    before = state(factory)
    response = client.put(f"/api/hazards/{row['id']}", json={
        "title": "不得部分写入", "deadline": (NOW + timedelta(days=days)).isoformat(),
    })
    assert response.status_code == 422, response.text
    assert state(factory) == before
    limit = discovered + timedelta(days=days)
    response = client.put(f"/api/hazards/{row['id']}", json={"deadline": limit.isoformat() + "Z"})
    assert response.status_code == 200, response.text
    assert datetime.fromisoformat(response.json()["data"]["deadline"]) == limit


def test_level_upgrade_rejection_is_atomic(api):
    client, factory, _ = api
    row = create(client, deadline=(NOW + timedelta(days=30)).isoformat())
    before = state(factory)
    response = client.put(f"/api/hazards/{row['id']}", json={"level": "MAJOR", "title": "不能偷改"})
    assert response.status_code == 422, response.text
    assert state(factory) == before
    response = client.put(f"/api/hazards/{row['id']}", json={
        "level": "MAJOR", "deadline": (NOW + timedelta(days=14)).isoformat(),
    })
    assert response.status_code == 200, response.text
    assert response.json()["data"]["level"] == "MAJOR"
    assert datetime.fromisoformat(response.json()["data"]["deadline"]) == NOW + timedelta(days=14)


def test_null_level_is_rejected_without_writes(api):
    client, factory, _ = api
    row = create(client, "MAJOR")
    before = state(factory)
    response = client.put(f"/api/hazards/{row['id']}", json={"level": None, "title": "不能偷改"})
    assert response.status_code == 422, response.text
    assert state(factory) == before


@pytest.mark.parametrize("level", ["MAJOR", "GENERAL"])
def test_update_normalizes_timezone_and_rejects_one_microsecond_over_limit(api, level):
    client, factory, _ = api
    days = 14 if level == "MAJOR" else 30
    row = create(client, level, deadline=(NOW + timedelta(days=1)).isoformat())
    limit = (NOW + timedelta(days=days)).replace(tzinfo=timezone.utc)
    encoded = limit.astimezone(timezone(timedelta(hours=-5)))
    before = state(factory)
    response = client.put(f"/api/hazards/{row['id']}", json={
        "deadline": (encoded + timedelta(microseconds=1)).isoformat(),
    })
    assert response.status_code == 422, response.text
    assert state(factory) == before
    response = client.put(f"/api/hazards/{row['id']}", json={"deadline": encoded.isoformat()})
    assert response.status_code == 200, response.text
    assert datetime.fromisoformat(response.json()["data"]["deadline"]) == limit.replace(tzinfo=None)


def test_downgrade_keeps_existing_shorter_deadline(api):
    client, _, _ = api
    short = NOW + timedelta(days=7)
    row = create(client, "MAJOR", deadline=short.isoformat())
    response = client.put(f"/api/hazards/{row['id']}", json={"level": "GENERAL"})
    assert response.status_code == 200, response.text
    assert datetime.fromisoformat(response.json()["data"]["deadline"]) == short


@pytest.mark.parametrize("same_level", [False, True])
@pytest.mark.parametrize("old_deadline", [None, NOW + timedelta(days=60)])
def test_legacy_records_still_allow_unrelated_updates(api, old_deadline, same_level):
    client, factory, _ = api
    row = create(client)
    legacy(factory, row["id"], deadline=old_deadline)
    changes = {"title": "仍可补充说明"}
    if same_level:
        changes["level"] = "GENERAL"
    response = client.put(f"/api/hazards/{row['id']}", json=changes)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["title"] == "仍可补充说明"
    assert data["deadline"] == (old_deadline.isoformat() if old_deadline else None)
    with factory() as db:
        assert db.get(Hazard, row["id"]).deadline == old_deadline


def test_explicit_update_cannot_keep_legacy_overlong_deadline(api):
    client, factory, _ = api
    row = create(client)
    invalid = NOW + timedelta(days=60)
    legacy(factory, row["id"], deadline=invalid)
    before = state(factory)
    response = client.put(f"/api/hazards/{row['id']}", json={"deadline": invalid.isoformat()})
    assert response.status_code == 422, response.text
    assert state(factory) == before


@pytest.mark.parametrize("level,days", [("MAJOR", 14), ("GENERAL", 30)])
def test_null_update_resets_default_from_original_discovery(api, level, days):
    client, factory, _ = api
    row = create(client, level)
    discovered = NOW - timedelta(days=3)
    legacy(factory, row["id"], reported_at=discovered)
    response = client.put(f"/api/hazards/{row['id']}", json={"deadline": None})
    assert response.status_code == 200, response.text
    assert datetime.fromisoformat(response.json()["data"]["deadline"]) == discovered + timedelta(days=days)


def test_level_change_fills_legacy_missing_deadline(api):
    client, factory, _ = api
    row = create(client)
    legacy(factory, row["id"], deadline=None)
    response = client.put(f"/api/hazards/{row['id']}", json={"level": "MAJOR"})
    assert response.status_code == 200, response.text
    assert datetime.fromisoformat(response.json()["data"]["deadline"]) == NOW + timedelta(days=14)


def test_closed_record_cannot_be_changed(api):
    client, factory, _ = api
    row = create(client)
    legacy(factory, row["id"], status=HazardStatus.VERIFIED)
    before = state(factory)
    assert client.put(f"/api/hazards/{row['id']}", json={"deadline": None}).status_code == 400
    assert state(factory) == before


@pytest.mark.parametrize("first,competing", [
    ({"deadline": (NOW + timedelta(days=30)).isoformat()}, {"level": "MAJOR"}),
    ({"level": "MAJOR"}, {"deadline": (NOW + timedelta(days=30)).isoformat()}),
])
def test_competing_level_and_deadline_update_rejects_stale_write(api, monkeypatch, first, competing):
    client, factory, _ = api
    row = create(client, deadline=(NOW + timedelta(days=7)).isoformat())
    path = f"/api/hazards/{row['id']}"
    original = hazards.deadline_for
    after_competing = None

    def interleave(*args, **kwargs):
        nonlocal after_competing
        deadline = original(*args, **kwargs)
        if after_competing is None:
            # 只调度真实请求的交错时机，不替换校验或数据库结果。
            after_competing = {}
            response = client.put(path, json=competing)
            assert response.status_code == 200, response.text
            after_competing = state(factory)
        return deadline

    monkeypatch.setattr(hazards, "deadline_for", interleave)
    response = client.put(path, json={**first, "title": "过时请求不得部分写入"})
    assert response.status_code == 409, response.text
    assert state(factory) == after_competing
    # 刷新后的请求重新按最新等级/期限校验，不能简单重试绕过上限。
    assert client.put(path, json=first).status_code == 422
    assert state(factory) == after_competing


def test_update_cannot_overwrite_concurrent_closure(api, monkeypatch):
    client, factory, headers = api
    row = create(client)
    path = f"/api/hazards/{row['id']}"
    original = hazards.deadline_for
    after_closure = None

    def interleave(*args, **kwargs):
        nonlocal after_closure
        deadline = original(*args, **kwargs)
        if after_closure is None:
            after_closure = {}
            response = client.post(path + "/rectify", json={"rectification_measure": "模拟整改完成"})
            assert response.status_code == 200, response.text
            response = client.post(path + "/verify", headers=headers["SAFETY_OFFICER"], json={
                "verifier": "测试复查员", "verification_notes": "模拟复查通过", "passed": True,
            })
            assert response.status_code == 200, response.text
            after_closure = state(factory)
        return deadline

    monkeypatch.setattr(hazards, "deadline_for", interleave)
    response = client.put(path, json={
        "title": "关闭后不得偷改", "deadline": (NOW + timedelta(days=10)).isoformat(),
    })
    assert response.status_code == 409, response.text
    assert state(factory) == after_closure
    assert client.put(path, json={"deadline": None}).status_code == 400
    assert state(factory) == after_closure


@pytest.mark.parametrize("level,days", [("MAJOR", -1), ("MAJOR", 0), ("MAJOR", 15),
                                        ("MAJOR", 60), ("GENERAL", -1), ("GENERAL", 0),
                                        ("GENERAL", 31), ("GENERAL", 60)])
def test_conversion_rejects_invalid_days(api, level, days):
    client, factory, _ = api
    record_id = started_record(api)
    assert submit(client, record_id).status_code == 200
    before = state(factory)
    response = client.post(f"/api/safety-checks/records/{record_id}/convert-hazard", json={
        "seq": 1, "category": "MECHANICAL", "level": level, "deadline_days": days,
    })
    assert response.status_code == 422, response.text
    assert state(factory) == before


@pytest.mark.parametrize("level,days", [("MAJOR", 1), ("MAJOR", 14), ("GENERAL", 1), ("GENERAL", 30)])
def test_conversion_accepts_valid_custom_days(api, level, days):
    client, factory, _ = api
    record_id = started_record(api)
    assert submit(client, record_id).status_code == 200
    response = client.post(f"/api/safety-checks/records/{record_id}/convert-hazard", json={
        "seq": 1, "category": "MECHANICAL", "level": level, "deadline_days": days,
    })
    assert response.status_code == 200, response.text
    with factory() as db:
        row = db.get(Hazard, response.json()["data"]["hazard_id"])
        assert row.deadline == row.reported_at + timedelta(days=days)


@pytest.mark.parametrize("level,days", [("MAJOR", 14), ("GENERAL", 30)])
@pytest.mark.parametrize("explicit_null", [False, True])
def test_conversion_default_uses_single_clock_anchor(api, monkeypatch, level, days, explicit_null):
    client, factory, _ = api
    record_id = started_record(api)
    assert submit(client, record_id).status_code == 200
    ticks = iter([NOW, NOW + timedelta(seconds=1)])

    class TickingClock(datetime):
        @classmethod
        def utcnow(cls):
            return next(ticks)

    monkeypatch.setattr(safety_checks, "datetime", TickingClock)
    request = {"seq": 1, "category": "MECHANICAL", "level": level}
    if explicit_null:
        request["deadline_days"] = None
    response = client.post(f"/api/safety-checks/records/{record_id}/convert-hazard", json=request)
    assert response.status_code == 200, response.text
    with factory() as db:
        row = db.get(Hazard, response.json()["data"]["hazard_id"])
        assert row.deadline == row.reported_at + timedelta(days=days)


def external_payload(**extra):
    return {"external_no": "DF-DEADLINE-1", "title": "模拟设备缺陷", "severity": "CRITICAL", **extra}


def receive(client, **extra):
    client.app.include_router(integration.router)
    return client.post("/api/integration/hazards", headers={
        "X-Integration-Secret": "deadline-integration-test-key",
    }, json=external_payload(**extra))


@pytest.mark.parametrize("offset", [8, -5])
@pytest.mark.parametrize("severity,days", [("CRITICAL", 14), ("MINOR", 30)])
def test_integration_stores_offset_discovery_as_utc(api, severity, days, offset):
    client, factory, _ = api
    discovered = NOW.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=offset)))
    response = receive(client, severity=severity, reported_at=discovered.isoformat())
    assert response.status_code == 200, response.text
    with factory() as db:
        row = db.get(Hazard, response.json()["data"]["id"])
        assert row.reported_at == NOW
        assert row.deadline == NOW + timedelta(days=days)


def test_integration_default_uses_single_clock_anchor(api, monkeypatch):
    client, factory, _ = api
    ticks = iter([NOW, NOW + timedelta(seconds=1)])

    class TickingClock(datetime):
        @classmethod
        def utcnow(cls):
            return next(ticks)

    monkeypatch.setattr(integration, "datetime", TickingClock)
    response = receive(client)
    assert response.status_code == 200, response.text
    with factory() as db:
        row = db.get(Hazard, response.json()["data"]["id"])
        assert row.deadline == row.reported_at + timedelta(days=14)


def test_duplicate_integration_preserves_original_deadline(api):
    client, factory, _ = api
    first = receive(client)
    assert first.status_code == 200, first.text
    before = state(factory)
    response = receive(client, severity="MINOR", reported_at=(NOW + timedelta(days=60)).isoformat())
    assert response.status_code == 200, response.text
    assert response.json()["data"]["duplicated"] is True
    assert response.json()["data"]["id"] == first.json()["data"]["id"]
    assert state(factory) == before


def test_integration_unrepresentable_default_returns_422_without_writes(api):
    client, factory, _ = api
    before = state(factory)
    response = receive(client, reported_at="9999-12-31T23:59:59Z")
    assert response.status_code == 422, response.text
    assert state(factory) == before
