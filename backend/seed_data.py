"""生成演示数据：admin 账号 + 若干隐患记录"""
import random
from datetime import datetime, timedelta

from app.database import SessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.hazard import Hazard, HazardArea, HazardCategory, HazardLevel, HazardStatus
from app.api.deps import hash_password
from app.utils.helpers import generate_hazard_code


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


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # admin
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(
                username="admin",
                hashed_password=hash_password("admin123"),
                role=UserRole.ADMIN,
                department="安环部",
                is_active=True,
            ))
            db.commit()
            print("✓ admin 已创建")

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
            print(f"✓ 已生成 {len(HAZARD_TEMPLATES)} 条隐患记录")
        else:
            print("- 隐患数据已存在，跳过")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
