"""生成演示数据：4 个角色账号 + 隐患 + 两票 + 安全检查样例"""
import json
import random
from datetime import datetime, timedelta, date

from app.database import SessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.hazard import Hazard, HazardArea, HazardCategory, HazardLevel, HazardStatus
from app.models.ticket import (
    WorkTicket, WorkTicketType, WorkTicketStatus,
    OperationTicket, OperationTicketStatus,
)
from app.models.safety_check import (
    SafetyCheckPlan, SafetyCheckRecord,
    CheckFrequency, CheckPlanStatus, CheckRecordStatus,
)
from app.api.deps import hash_password
from app.utils.helpers import (
    generate_hazard_code, generate_work_ticket_code,
    generate_operation_ticket_code, generate_safety_check_code,
)


HAZARD_TEMPLATES = [
    ("锅炉本体保温层局部脱落", "锅炉#2尾部烟道保温层出现约2平米脱落，存在烫伤风险", HazardArea.BOILER, HazardCategory.PRESSURE_VESSEL, HazardLevel.GENERAL),
    ("高压配电柜接地线松动", "6kV高压配电室3号柜接地线连接螺栓松动", HazardArea.ELECTRICAL, HazardCategory.ELECTRICAL_SAFETY, HazardLevel.MAJOR),
    ("输煤皮带防护罩缺失", "输煤皮带3A段防护罩被拆除未复位", HazardArea.FUEL, HazardCategory.MECHANICAL, HazardLevel.GENERAL),
    ("汽机房高处作业平台护栏破损", "汽机房A排15米平台护栏立柱锈蚀变形", HazardArea.TURBINE, HazardCategory.WORK_AT_HEIGHT, HazardLevel.MAJOR),
    ("化学车间盐酸罐渗漏", "31%盐酸储罐底部法兰处发现渗漏痕迹", HazardArea.CHEMICAL, HazardCategory.CHEMICAL_HAZARD, HazardLevel.MAJOR),
    ("脱硫塔检修平台无安全网", "1号脱硫塔检修平台下方未拉设安全网", HazardArea.DESULFURIZATION, HazardCategory.WORK_AT_HEIGHT, HazardLevel.GENERAL),
    ("除尘器灰斗动火作业未办票", "现场发现电焊作业，未办理动火作业票", HazardArea.ASH_HANDLING, HazardCategory.HOT_WORK, HazardLevel.MAJOR),
    ("消防器材过期", "主厂房0米层灭火器超过年检日期", HazardArea.MAIN_PLANT, HazardCategory.FIRE_PROTECTION, HazardLevel.GENERAL),
    ("电缆桥架积灰严重", "2号机组电缆夹层积灰超10cm，存在火灾隐患", HazardArea.ELECTRICAL, HazardCategory.FIRE_PROTECTION, HazardLevel.GENERAL),
    ("冷却塔进入未设监护人", "运行人员独自进入冷却塔检查，未设置监护", HazardArea.COOLING_TOWER, HazardCategory.CONFINED_SPACE, HazardLevel.GENERAL),
]

REPORTERS = ["张三", "李四", "王五", "赵六", "钱七"]
DEPARTMENTS = ["运行部", "检修部", "化学部", "燃料部", "电气部"]


USER_TEMPLATES = [
    ("admin", "admin123", UserRole.ADMIN, "安环部"),
    ("officer", "officer123", UserRole.SAFETY_OFFICER, "安环部"),
    ("operator", "operator123", UserRole.OPERATOR, "运行部"),
    ("viewer", "viewer123", UserRole.VIEWER, "办公室"),
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 用户
        for uname, pwd, role, dept in USER_TEMPLATES:
            if db.query(User).filter(User.username == uname).first():
                continue
            db.add(User(
                username=uname,
                hashed_password=hash_password(pwd),
                role=role,
                department=dept,
                is_active=True,
            ))
        db.commit()
        print(f"[OK] 用户已就绪（admin/officer/operator/viewer，密码用户名+123）")

        # 隐患数据
        if db.query(Hazard).count() == 0:
            now = datetime.utcnow()
            for i, (title, desc, area, cat, lvl) in enumerate(HAZARD_TEMPLATES, 1):
                reported_at = now - timedelta(days=random.randint(0, 30))
                deadline = reported_at + timedelta(days=14 if lvl == HazardLevel.MAJOR else 30)
                # 随机分配状态
                roll = random.random()
                if roll < 0.3:
                    status = HazardStatus.PENDING
                    rectified_at = None
                    verified_at = None
                elif roll < 0.6:
                    status = HazardStatus.IN_PROGRESS
                    rectified_at = None
                    verified_at = None
                elif roll < 0.8:
                    status = HazardStatus.RECTIFIED
                    rectified_at = reported_at + timedelta(days=random.randint(3, 10))
                    verified_at = None
                else:
                    status = HazardStatus.VERIFIED
                    rectified_at = reported_at + timedelta(days=random.randint(3, 10))
                    verified_at = rectified_at + timedelta(days=random.randint(1, 5))

                h = Hazard(
                    hazard_code=generate_hazard_code(i),
                    title=title,
                    description=desc,
                    area=area,
                    category=cat,
                    level=lvl,
                    reporter=random.choice(REPORTERS),
                    department=random.choice(DEPARTMENTS),
                    reported_at=reported_at,
                    assignee=random.choice(REPORTERS),
                    assignee_dept=random.choice(DEPARTMENTS),
                    deadline=deadline,
                    rectification_measure="已完成现场整改，更换损坏部件并复核合规性" if rectified_at else None,
                    rectified_at=rectified_at,
                    verifier="安全员" if verified_at else None,
                    verified_at=verified_at,
                    verification_notes="复查通过，整改符合要求" if verified_at else None,
                    status=status,
                )
                db.add(h)
            db.commit()
            print(f"[OK] 已生成 {len(HAZARD_TEMPLATES)} 条隐患记录")
        else:
            print("[--] 隐患数据已存在，跳过")

        # 两票样例
        if db.query(WorkTicket).count() == 0:
            now = datetime.utcnow()
            samples = [
                (WorkTicketType.ELECTRICAL_FIRST, "6kV配电柜母线检修",
                 "对6kV母线进行年度检修，包括清扫、绝缘测试、紧固螺栓",
                 "6kV高压配电室", "李四", "王五,赵六", "刘七", "运行甲班",
                 "1.断开上级电源；2.验电；3.挂接地线；4.悬挂警示牌；5.设置围栏",
                 "防止误送电，监护人全程在岗",
                 WorkTicketStatus.IN_PROGRESS),
                (WorkTicketType.HOT_WORK, "锅炉#2省煤器焊接补漏",
                 "省煤器顶部弯头泄漏，需现场动火补焊",
                 "锅炉#2省煤器顶部", "张三", "马八,孙九", "周十", "运行乙班",
                 "1.清理现场可燃物；2.配备消防器材；3.设置火花隔离板；4.动火监护人在岗",
                 "高温部件未完全冷却风险，配灭火器2具",
                 WorkTicketStatus.COMPLETED),
                (WorkTicketType.CONFINED_SPACE, "脱硫塔内部清淤",
                 "1号脱硫塔停运清淤，进入塔体作业",
                 "1号脱硫塔", "王五", "陈一,吴二", "钱三", None,
                 "1.通风换气30分钟；2.检测有毒气体；3.外部监护；4.系安全绳",
                 "有限空间作业，缺氧/中毒风险",
                 WorkTicketStatus.PENDING_APPROVAL),
            ]
            for i, (ttype, title, content, loc, issuer, members, leader, supervisor, measures, risks, status) in enumerate(samples, 1):
                t = WorkTicket(
                    ticket_code=generate_work_ticket_code(i),
                    ticket_type=ttype, title=title, work_content=content,
                    work_location=loc, issuer=issuer, work_leader=leader,
                    work_members=members, supervisor=supervisor,
                    planned_start=now - timedelta(days=2),
                    planned_end=now + timedelta(days=1),
                    safety_measures=measures, risk_points=risks,
                    status=status,
                )
                if status in (WorkTicketStatus.APPROVED, WorkTicketStatus.IN_PROGRESS, WorkTicketStatus.COMPLETED):
                    t.approver = "officer"
                    t.approved_at = now - timedelta(days=2, hours=2)
                    t.approval_notes = "安全措施齐全，同意作业"
                if status in (WorkTicketStatus.IN_PROGRESS, WorkTicketStatus.COMPLETED):
                    t.permitter = "运行值长"
                    t.actual_start = now - timedelta(days=1, hours=20)
                if status == WorkTicketStatus.COMPLETED:
                    t.closer = "李四"
                    t.closed_at = now - timedelta(hours=4)
                    t.actual_end = t.closed_at
                    t.close_notes = "作业完成，现场清理完毕"
                db.add(t)
            db.commit()
            print(f"[OK] 已生成 {len(samples)} 条工作票样例")

        if db.query(OperationTicket).count() == 0:
            now = datetime.utcnow()
            op_samples = [
                ("1号机组并网操作", "1号发电机", "张三", "李四", "刘值长",
                 [
                     {"step": 1, "content": "确认机组转速达到3000rpm", "done": True, "checked_at": (now-timedelta(hours=4)).isoformat()},
                     {"step": 2, "content": "投入励磁系统", "done": True, "checked_at": (now-timedelta(hours=4)).isoformat()},
                     {"step": 3, "content": "电压调整至额定值", "done": True, "checked_at": (now-timedelta(hours=4)).isoformat()},
                     {"step": 4, "content": "频率与电网同步", "done": True, "checked_at": (now-timedelta(hours=4)).isoformat()},
                     {"step": 5, "content": "合上发电机出口开关", "done": True, "checked_at": (now-timedelta(hours=4)).isoformat()},
                 ],
                 OperationTicketStatus.COMPLETED),
                ("2号给水泵切换", "2A→2B给水泵", "王五", "赵六", "刘值长",
                 [
                     {"step": 1, "content": "启动备用泵2B并热备用", "done": False},
                     {"step": 2, "content": "确认2B泵出口压力正常", "done": False},
                     {"step": 3, "content": "缓慢开启2B出口阀", "done": False},
                     {"step": 4, "content": "缓慢关闭2A出口阀", "done": False},
                     {"step": 5, "content": "停止2A泵并隔离", "done": False},
                 ],
                 OperationTicketStatus.READY),
            ]
            for i, (title, target, operator, supervisor, issuer, steps, status) in enumerate(op_samples, 1):
                t = OperationTicket(
                    ticket_code=generate_operation_ticket_code(i),
                    title=title, operation_target=target,
                    operator=operator, supervisor=supervisor, issuer=issuer,
                    planned_at=now - timedelta(hours=6) if status == OperationTicketStatus.COMPLETED else now + timedelta(hours=2),
                    steps=json.dumps(steps, ensure_ascii=False),
                    status=status,
                )
                if status in (OperationTicketStatus.READY, OperationTicketStatus.EXECUTING, OperationTicketStatus.COMPLETED):
                    t.reviewer = "officer"
                    t.reviewed_at = now - timedelta(hours=7)
                    t.review_notes = "步骤清晰，同意执行"
                if status == OperationTicketStatus.COMPLETED:
                    t.started_at = now - timedelta(hours=5)
                    t.completed_at = now - timedelta(hours=4)
                db.add(t)
            db.commit()
            print(f"[OK] 已生成 {len(op_samples)} 条操作票样例")

        # 安全检查计划 + 几条检查记录
        if db.query(SafetyCheckPlan).count() == 0:
            plan_samples = [
                ("锅炉区周巡检", HazardArea.BOILER, CheckFrequency.WEEKLY, "运行部",
                 "锅炉区每周一次安全巡查，重点检查保温、阀门、压力表",
                 [
                     {"seq": 1, "content": "锅炉本体保温层完好性", "standard": "无明显脱落、起皮、热点", "weight": 1.0},
                     {"seq": 2, "content": "安全阀手柄/铅封状态", "standard": "铅封完好，手柄无卡涩", "weight": 1.0},
                     {"seq": 3, "content": "压力表指示与零点", "standard": "在量程内，无卡针", "weight": 1.0},
                     {"seq": 4, "content": "炉膛观察孔密封", "standard": "无漏烟，盖板齐全", "weight": 0.8},
                     {"seq": 5, "content": "炉墙温度异常点排查", "standard": "无超过 60℃ 的外表面", "weight": 1.0},
                 ]),
                ("电气区月度专项检查", HazardArea.ELECTRICAL, CheckFrequency.MONTHLY, "电气部",
                 "6kV以上电气设备月度专项检查",
                 [
                     {"seq": 1, "content": "高压开关柜接地完好性", "standard": "接地线连接紧固，无锈蚀", "weight": 1.0},
                     {"seq": 2, "content": "二次回路标识规范", "standard": "标牌齐全清晰", "weight": 0.5},
                     {"seq": 3, "content": "电缆夹层防火封堵", "standard": "封堵完整无破损", "weight": 1.0},
                     {"seq": 4, "content": "应急照明可用性", "standard": "停电自启动，电池电压正常", "weight": 0.8},
                 ]),
                ("化学储罐区季度检查", HazardArea.CHEMICAL, CheckFrequency.QUARTERLY, "化学部",
                 "酸碱储罐及管线季度专项",
                 [
                     {"seq": 1, "content": "酸碱储罐液位计指示", "standard": "刻度清晰，无漏液", "weight": 1.0},
                     {"seq": 2, "content": "围堰防腐层", "standard": "无明显腐蚀剥落", "weight": 1.0},
                     {"seq": 3, "content": "事故喷淋装置", "standard": "出水通畅，铭牌完好", "weight": 1.0},
                 ]),
            ]
            plans = []
            for name, area, freq, dept, desc, items in plan_samples:
                p = SafetyCheckPlan(
                    name=name, area=area.value, frequency=freq, owner_dept=dept,
                    description=desc,
                    item_template=json.dumps(items, ensure_ascii=False),
                    status=CheckPlanStatus.ACTIVE,
                )
                db.add(p)
                plans.append(p)
            db.commit()
            for p in plans:
                db.refresh(p)
            print(f"[OK] 已生成 {len(plans)} 个检查计划")

            # 为第一个计划生成几条检查记录（含已完成的，附不符合项）
            today = date.today()
            rec_seq = 0
            for offset in (-7, 0, 7):
                rec_seq += 1
                rec = SafetyCheckRecord(
                    record_code=generate_safety_check_code(rec_seq),
                    plan_id=plans[0].id,
                    scheduled_date=today + timedelta(days=offset),
                    total_items=5,
                    nonconformant_count=0,
                    status=CheckRecordStatus.PENDING,
                )
                if offset == -7:
                    # 已完成（含一个不符合）
                    results = [
                        {"seq": 1, "content": "锅炉本体保温层完好性", "standard": "无明显脱落",
                         "conformant": False, "notes": "尾部烟道保温层局部脱落约2平米", "hazard_id": None},
                        {"seq": 2, "content": "安全阀手柄/铅封状态", "standard": "铅封完好",
                         "conformant": True, "notes": None, "hazard_id": None},
                        {"seq": 3, "content": "压力表指示与零点", "standard": "在量程内",
                         "conformant": True, "notes": None, "hazard_id": None},
                        {"seq": 4, "content": "炉膛观察孔密封", "standard": "无漏烟",
                         "conformant": True, "notes": None, "hazard_id": None},
                        {"seq": 5, "content": "炉墙温度异常点排查", "standard": "无超过60℃外表",
                         "conformant": True, "notes": None, "hazard_id": None},
                    ]
                    rec.result_items = json.dumps(results, ensure_ascii=False)
                    rec.total_items = len(results)
                    rec.nonconformant_count = 1
                    rec.summary = "整体合格，1项不符合（保温层），已通知整改"
                    rec.inspector = "operator"
                    rec.started_at = datetime.utcnow() - timedelta(days=7, hours=2)
                    rec.completed_at = datetime.utcnow() - timedelta(days=7)
                    rec.status = CheckRecordStatus.COMPLETED
                db.add(rec)
            db.commit()
            print(f"[OK] 已生成 3 条检查记录（1 条已完成 + 1 条今日待执行 + 1 条下周）")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
