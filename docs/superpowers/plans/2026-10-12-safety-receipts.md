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
- [ ] 实际 HTTP 输入/相同内容/冲突/旧映射/人工处置/坏键/事务失败回归，先确认 RED。
- [ ] 实现收据与冲突拒绝、新表注册/启动，完整原有 68 项与新回归通过；提交候选。

### Task 2 · 两数据库与跨系统故障证据

Files: tests/postgresql/test_integration_receipts.py、.github/workflows/quality.yml；设备端 tests/test_safety_delivery.py 运行两个独立服务。
- [ ] 实际 SQLite/PostgreSQL 同/异键竞争、编号碰撞及故障注入 RED；加入 PostgreSQL CI。
- [ ] 完整 backend/前端构建，设备端真实 HTTP 正常/断线/重启/内容变更对接通过，推送。
- [ ] 随整批一次 fresh-context 审查；重要修复 RED→GREEN 后候选 CI/合并/main CI；发布真实 SHA 与中央签收。

## 执行台账

基线 e5e62e77ea0d01c7c24bea790d79e51a3b3f18d1，完整 68 passed。工作分支 upgrade/safety-integration-20261012。用户已有自主执行授权，方案/检查点可随阶段核对；无重复许可等待。Pre-flight: 发送端 ACK 消费来源/单号/id/hazard_no，接收端必须同时提供；发送端消息不可变，接收端对原消息重放不重置人工处置。
