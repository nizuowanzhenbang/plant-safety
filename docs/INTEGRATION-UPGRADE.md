# 安全联动接收升级与恢复（PP-042）

适用于 PP-041 原子收据与统一隐患编号版本及后续兼容版本。核对基线：业务 [6f12503](https://github.com/nizuowanzhenbang/plant-safety/commit/6f12503f00fdd485a55e737f17d08e8ff8b833f0)，本文编写时 main 为 aed22d627120c6c902878f6c6b8a28b50fef72c5。使用个人构造数据演练；实际部署的进程管理器、路径、数据库和凭据由部署清单确定。

## 已核对的升级行为

- [启动入口](../backend/app/main.py)调用 `Base.metadata.create_all`；新建 `integration_receipts` 与 `hazard_number_sequences`。它不会迁移已有表的缺列、修复已有错误约束，也没有 Alembic 升降级命令。发现不兼容结构应停止切换并单独评估。
- [收据模型](../backend/app/models/integration_receipt.py)以来源系统和来源单号唯一，保存原消息、指纹与隐患引用。隐患和收据同事务提交。旧隐患不会启动时批量回填；首次原消息重放仅在已有投影一致且来源唯一时补收据，否则 409，需人工核对。
- [编号分配器](../backend/app/utils/hazard_numbers.py)供人工登记、检查转隐患、联动接收三个入口共用。某日第一次使用时从该日已有合法数字后缀取最大值；此后只推进日序号。旧进程不更新新序号表，混跑可能撞号，必须统一切换所有写入进程。
- 默认数据库是相对工作目录的 `sqlite:///./plant_safety.db`，配置读取当前工作目录的 `.env`。升级前记录实际工作目录与解析后的数据库目标，不能用一个空库启动成功来证明原库升级成功。`/health`只返回应用信息，不查询数据库。
- 启动会在没有 `admin` 时创建默认管理员。升级不运行 `seed_data.py`，并核对已有用户、密钥和账户策略；不要误连空库。

## 维护窗口与备份

1. 记录旧/新完整代码 SHA、Python 与依赖版本、数据库类型和目标、启动工作目录、服务实例/后台脚本清单、当前隐患/收据/序号行数与待发送记录清单。保存部署配置和密钥到受控备份位置，记录中不输出秘密值。
2. 关闭安全端写入入口并排空在途请求。停止所有安全 API worker、重载进程、旧版本容器、检查转换脚本和直接写库作业；确认无旧连接写入。仅停止某一个 worker 或关闭网页不足以停写。
3. 暂停设备端相关发送和重试。仅设置 `SCHEDULER_ENABLED=false` 不能阻止创建缺陷时即时发送及手动重推，配置更改也需要重启；维护入口应同时拦截这些发送路径，或停止相关设备后端进程。已保存 outbox 保留，不清空队列、不生成新来源单号。
4. 在停写后备份整个安全数据库，另备份设备数据库/发送账本，记录同一维护窗口的两个时间点。数据库快照是各自一致的，不是跨库原子快照。外部照片 URL 所指资源不在数据库备份中，应按实际存储另行保护。
5. 生成备份文件散列和表行数清单，在独立目标恢复并核对后才继续升级。不要把“文件存在”或“导出命令退出 0”当恢复验收。

SQLite 示例（在确认实际路径后设置 `SAFETY_DB_FILE`、`SAFETY_BACKUP_FILE`；目标必须不存在，使用 Python SQLite backup API，不复制正在写的主文件）：

```bash
python - <<'PY'
import hashlib
import os
from pathlib import Path
import sqlite3

source = Path(os.environ["SAFETY_DB_FILE"]).resolve(strict=True)
target = Path(os.environ["SAFETY_BACKUP_FILE"]).absolute()
if source == target:
    raise SystemExit("备份不能覆盖源库")
with target.open("xb"):
    pass
with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
        assert dst.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert dst.execute("PRAGMA foreign_key_check").fetchall() == []
print(hashlib.sha256(target.read_bytes()).hexdigest())
PY
```

若备份中断，隔离该不完整文件，换新目标重新执行，不把它列为可用备份。按本库实际存在的表记录行数；旧版本尚无新表是预期情况。

PostgreSQL 使用与服务端兼容的客户端和预配置 libpq 服务（`PGSERVICE`/`PGSERVICEFILE` 与受限 `.pgpass`），不要把口令放入命令或日志：

```bash
# PGSERVICE 指向已核对的安全源库；SAFETY_BACKUP_FILE 是不存在的新文件
( set -o noclobber; pg_dump --format=custom > "$SAFETY_BACKUP_FILE" ) &&
pg_restore --list "$SAFETY_BACKUP_FILE" &&
sha256sum "$SAFETY_BACKUP_FILE"
```

确认上一步成功后，用另一个 libpq 服务 `safety_restore_check` 指向提前创建且与原库隔离的空库；核对目标主机、库名和权限后执行：

```bash
pg_restore --exit-on-error --single-transaction --no-owner --no-privileges \
  --dbname='service=safety_restore_check' "$SAFETY_BACKUP_FILE"
```

该演练省略所有者/授权，部署恢复时由已保存的权限清单恢复相应角色和授权。不要对原库使用 `--clean`，不要覆盖原库来试验备份。

## 单版本升级与放行

1. 在隔离恢复库上部署选定新 SHA 与依赖，保持外部发送/真实访问隔离；先启动一个新进程，使启动建表执行一次，再核对两个新增表、唯一约束、外键以及既有表行数。首次新编号之前日序号表可以为空。
2. 检查启动日志、已有用户与一条既有隐患的读回。使用合成场景验证人工创建、检查转换、集成接收三个入口产生不同且合法的编号。
3. 用同一来源/单号/同内容发送两次：第二次返回同一正整数隐患 ID 和隐患号，`duplicated=true`，仅一条收据与隐患。修改内容重放应 409，原记录保持。验证查询 `GET /api/integration/hazards/by-external` 与 ACK 的来源和单号对应。测试在隔离库进行，不能在真实账本里伪造记录。
4. 实际窗口中确认旧进程全部停止后，按同一新 SHA 启动一个安全端进程，核对真实数据库目标、表结构和读回；再启动其余同版本进程。不得滚动混跑旧编号算法。
5. 先放行安全端读写，再恢复设备发送/重试。按原来源键核对少量既有待发送记录，确保 ACK 后本地标记成功且无重复隐患；记录失败/跳过/409，保留原消息交人工处理。不能通过删收据、修改原单号、重置内容绕过冲突。
6. 清单全部通过才结束窗口；记录新 SHA、窗口起止、备份散列、执行者、核验结果和待对账项。本文不设未经测量的停机时长承诺。

## 失败恢复

**尚未放行新写入：** 保持入口关闭，停掉全部新进程。保留失败后的数据库副本及日志。在独立空目标恢复升级前完整备份，核对散列、完整性/外键、各表行数与原记录。将所有旧版本进程统一指向已核对恢复目标并验证，再有序放行。不要只删除两个新表“降级”，也不要覆盖唯一备份。

**已放行写入或已有 ACK：** 先再次停写和暂停所有发送，保存两端当前完整快照与已确认/待发送清单。优先在保留当前数据的情况下前向修复。若必须回到升级前快照，先由维护负责人核对窗口内新增和修改，形成逐条恢复/重放清单；安全库回退可能丢失已 ACK 的隐患，而设备端已成功记录默认不会自动重发，不能假定“重启重试就恢复”。

恢复必须覆盖整个安全库，保持隐患、收据、编号序列及检查关联一致。仅回退隐患表会留下坏引用，单独回退序号会撞号。设备端也不可任意回退导致其他库存/采购等业务历史丢失。先在隔离副本演练对账结果，保留来源身份与原内容，核对已 ACK 映射仍存在后才放行；无法确定就保持受影响通路暂停并交接缺口。

## 本文验证范围

2026-10-27 逐项对照上述固定版本启动、配置、数据库、模型、编号和接收源码，以及现有 CI 配置。编写时云执行环境尚未可用，**本轮没有执行 SQLite/PostgreSQL 备份恢复、进程切换或现场升级演练**。PR 的现有后端/PostgreSQL/前端 CI 是代码回归，不能代替这些操作演练。上述命令是待在隔离目标验证的操作范例。PP-042 交付的是升级说明，不新增迁移器、备份服务或自动跨库恢复能力。
