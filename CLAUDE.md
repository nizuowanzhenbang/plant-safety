# Claude Code 项目规则

## 项目定位

发电厂安全生产管理系统。v1.0 聚焦隐患排查闭环，独立部署、独立数据库。

## 技术栈约束

- 后端：FastAPI + SQLAlchemy + Pydantic v2，沿用 coal-transport-monitor / coal-quality-monitor 的同款结构（api/models/schemas/services/utils 分层）
- 前端：React 18 + TypeScript + Ant Design 5 + ECharts + Zustand + Vite
- 数据库：SQLite（开发）/ PostgreSQL（生产）
- 认证：JWT (OAuth2PasswordBearer)
- 不引入额外框架（不上 NestJS / Django / Vue）

## 业务规则

- **隐患状态机**：`PENDING → IN_PROGRESS → RECTIFIED → VERIFIED`；超期自动 `OVERDUE`
- **重大隐患**：整改期限不可超过 14 天；一般隐患不超过 30 天
- **状态转换权限**（暂未强制，后续 v2 加角色校验）：
  - 登记：OPERATOR 及以上
  - 分派/提交整改：OPERATOR 及以上
  - 复查：SAFETY_OFFICER 及以上
  - 强制关闭/删除：ADMIN
- 隐患编号格式：`YH-YYYYMMDD-NNNN`，按全表序号顺序生成
- 区域和类别枚举不要轻易改字符串值（已写入数据库）

## 与已有系统的关系

本系统**独立运行**，不直接依赖 coal-transport-monitor / coal-quality-monitor。

未来 v4 可能加入闭环联动：
- 设备运维系统的工单可关联隐患
- 煤质/运输系统的预警可关联隐患（如铅封多次损坏 → 创建隐患）

## 代码风格

- 后端中文 docstring，schema/字段注释说明业务含义
- 前端 Ant Design 5 默认中文 locale，所有 label/按钮使用中文
- API 响应统一格式 `{code, message, data}`，使用 `utils.helpers.api_response`
- 分页统一用 `paginate_response`

## 开发流程

1. 改 models → migrations（暂用 `Base.metadata.create_all`，未来用 Alembic）
2. 改 schemas → 同步 frontend/src/types
3. 改 api → 同步 frontend/src/api
4. 改 pages → 测试 UI

## 已知简化

- 文件上传（隐患照片）暂存 URL 字段，未实现存储后端
- 通知（邮件/短信）暂未集成
- 没有角色权限拦截（仅依赖 get_current_user 校验登录）
- WebSocket 实时推送暂未加入（v2 加）
