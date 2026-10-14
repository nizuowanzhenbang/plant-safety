# 安全联动接收 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task.

**Goal:** PP-041 为 PP-040 配套提供原子、防重、内容冲突可见的安全隐患接收。
**Architecture:** integration_receipts 唯一自然键与 Hazard 同事务，保存规范请求内容和映射。重放读原收据；历史映射经核对接续；ACK 包含来源/单号。
**Tech Stack:** 既有 FastAPI/Pydantic/SQLAlchemy，SQLite/PostgreSQL；不引入框架。
**Spec:** ../specs/2026-10-12-safety-delivery.md（与设备端相同版本）。

## Global Constraints

- source_system/external_no 非空、最多 50；severity 仅 MINOR/MAJOR/CRITICAL。
- 同键同内容返回原 Hazard；同键内容不同 409；提交原子，编号碰撞有限重试，忙时 503 可重试。
- 保留整改原发现时间与 14/30 天规则，原人工处置不由消息重放覆盖。
- 新表通过 metadata.create_all 增加，不改 Hazard 列或清洗历史重复行；接收端先部署。

## Review Focus

时间/空值等价重放；相同和不同自然键并发；人工处置后相同消息；历史无指纹/重复键；提交后回执丢失/数据库异常不留半行。均纳入 owning test，若新输入超出范围保持非成功并可核对。

### Task 1 · 契约、事务收据与迁移启动

Files: backend/app/models/integration_receipt.py、api/integration.py、main.py；tests/test_integration_receipts.py。
Interfaces: normalized_payload(body)->dict；receive_hazard 固定自然键 ACK；lookup 返回相同身份。
- [x] 实际 HTTP 输入/相同内容/冲突/旧映射/人工处置/坏键/事务失败回归，先确认 RED。
- [x] 实现收据与冲突拒绝、新表注册/启动，完整原有 68 项与新回归通过；提交候选。

### Task 2 · 两数据库与跨系统故障证据

Files: tests/postgresql/test_integration_receipts.py、.github/workflows/quality.yml；设备端 tests/test_safety_delivery.py 运行两个独立服务。
- [x] 实际 SQLite/PostgreSQL 同/异键竞争、编号碰撞及故障注入 RED；加入 PostgreSQL CI。
- [x] 完整 backend/前端构建，设备端真实 HTTP 正常/断线/重启/内容变更对接通过，推送。
- [ ] 随整批一次 fresh-context 审查；重要修复 RED→GREEN 后候选 CI/合并/main CI；发布真实 SHA 与中央签收。

## 执行台账

基线 e5e62e77ea0d01c7c24bea790d79e51a3b3f18d1，完整 68 passed。工作分支 upgrade/safety-integration-20261012。用户已有自主执行授权，方案/检查点可随阶段核对；无重复许可等待。Pre-flight: 发送端 ACK 消费来源/单号/id/hazard_no，接收端必须同时提供；发送端消息不可变，接收端对原消息重放不重置人工处置。

## 接收实现阶段

实际42项新双数据库回归先40 failed/2 passed；附加事务写入失败/丢失映射和既有冲突不延长期限先4 failed/1 intentional skip。复现 a3c34386576dadc96ecf3aafd4f1de4c2e26ac00 已推送。实现后完整113 passed/1 skipped，跳过仅 PostgreSQL FK 已阻止的孤立映射人工损坏场景；SQLite 实际覆盖该拒绝。原有68项仍覆盖，新冲突请求明确409并保持原期限。

新表由 main 在 create_all 前注册，与隐患同事务；自然键唯一/hash/原请求保存；旧映射按可核对的标题描述/区域/类别/等级/人员/来源/显式发现时间核对；没有可验证的原 location/sla 字段不能反推，首次接续收据保存此次规范消息。人工修改新收据对应隐患后重放不回写处置。

Ruling: 历史无原消息的映射只核对已存投影，重复/不一致返回409 — 无法从旧 Hazard 重建全部原字段 — 未存的原字段无法证明，同步冲突需要人工核对，绝不任意取第一条或清洗历史。

反查新增 query 参数形式保留旧路径；支持 Unicode/含斜线的机器单号而不任意收窄旧输入范围。加入真实 PostgreSQL CI。ruff/前端构建通过；真正两应用协议验收和整批审查/发布仍待。


## 整批审查 Important 修正轮 · 2026-10-14

唯一一次fresh-context审查发现编号与人工/检查count规则不兼容：PG回滚序列空洞后两入口500。新HTTP回归先2 failed/2 passed，失败提交9752f18。接受Important R1，三个入口统一独立 hazard_number_sequences 日序号与原隐患事务；启动只增新表，不改旧列/历史记录，按当前日最大合法后缀接续，已提交号码删除后不复用。代价：新增小表、同日编号串行；需维护窗口统一切换进程，旧count写入进程不得混用。旧库增表/重复启动/9000高号/删除不复用另有双库回归。

整批其它Important R2/R3在设备计划完整记录，单次修复后不再启动整批审查。三项Minor明确延期：接收备份维护窗口具体操作说明、采购显式余量、日常界面显示已存跳过/失败原因。边界与成本见设备计划和中央证据。审查者Declined现场/性能/第三方/任意篡改恢复/跨库exactly-once，接受其范围边界，不声称这些已验收。


单次修正后最终完整后端119 passed/1 intentional skip（PG外键已阻止的人工损坏孤立映射）；ruff通过。新增双库旧表升级、重复启动、9000高号接续、已提交号码删除不复用均通过。第一次附加升级测试编辑因backend工作目录又带backend前缀而未写入，纠正路径后实际执行通过，不计业务失败。候选CI与集成仍待。
