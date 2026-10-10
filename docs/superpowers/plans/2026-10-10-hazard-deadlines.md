# 隐患整改期限 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 所有新增或明确调整的隐患期限遵循发现时间起算的重大 14 天、一般 30 天上限，并保留历史记录可维护性。

**Architecture:** 将 UTC 换算和上限校验集中到一个小工具；路由先计算有效等级/期限，校验通过后才修改模型。保留原有数据库、状态和关联机制。

**Tech Stack:** FastAPI、Pydantic 2、SQLAlchemy、pytest、React/Ant Design；不增加依赖。

**Spec:** `docs/DEADLINE-POLICY.md`。

## Global Constraints

- 重大最多 14 天、一般最多 30 天，从 reported_at 起算；边界包含等于。
- UTC naive 数据库存储不迁移；无关字段更新不改旧期限；reject 前不写模型。
- 原状态、权限、检查关联保护和集成重复返回语义不改变。

## Review Focus

- 带时区日期跨日：绝对时刻相同应得到同样判定和存储。
- 旧记录超限/无期限：无关修改仍可维护，不自动改写历史。
- 等级升降：使用有效等级和原发现时间，超限请求不能部分写入。
- 省略/null/0：默认、重置和非法天数应有不同结果。
- 重复集成与极端时间：不重设原记录，不产生 500 或半条记录。

## Task 1: 统一期限策略与真实入口回归

**Files:**
- Create: `backend/app/utils/hazard_deadlines.py`。
- Modify: `backend/app/api/hazards.py`、`safety_checks.py`、`integration.py`。
- Modify: `frontend/src/pages/HazardList.tsx`、`README.md`。
- Test: `backend/tests/test_hazard_deadlines.py`。

**Interfaces:**
- `deadline_for(level: HazardLevel, reported_at: datetime, deadline: datetime | None = None) -> datetime`：规范 UTC 并校验上限，错误返回 HTTP 422。
- `normalize_utc(value: datetime) -> datetime`：转为 UTC naive，处理无法表示的时间。
- 检查转换在调用同一规则前校验整数天数的正数和等级上限；更新使用持久化 discovered anchor。

- [ ] 先写真实 API 回归：`test_create_rejects_deadline_over_limit`、`test_update_uses_original_reported_at`、`test_level_upgrade_rejection_is_atomic`、`test_conversion_rejects_invalid_days`；拒绝后比较全部数据库字段。
- [ ] 运行新文件，确认上限和默认/时区缺口失败；保存 red 日志。
- [ ] 补缺省/null、等于上限/多 1 微秒、UTC 偏移、降级保留短期限、旧记录、单一时间锚点、集成重复和极端时间的实际入口回归。
- [ ] 实现工具和三个路由的最小修改；手工更新先计算有效值再写模型。
- [ ] 登记表显示默认/上限说明并禁用超上限日期；保留服务端最终校验。
- [ ] 运行完整 `python -m pytest tests -q`、Ruff 指定检查、前端生产构建与 diff 检查。
- [ ] 保存实际检查、边界和发布说明，提交推送；一次独立只读审查，必要修复后等待 PR 检查并按本轮授权集成。
- [ ] 回写中央 SUMMARY/CURRENT/TASKS/REPOSITORIES 和本轮日志；保存代码基线、交付 SHA、PR/CI 和下一步。

## 执行记录

在本轮中央日志记录每一步的实际结果，不依赖对话记忆。支持脚本资源在当前插件包中不可用，使用版本化计划、日志及 Git 提交作为接续台账。文档接入 PP-001 已完成，当前只实施 PP-010。
