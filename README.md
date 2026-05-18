# 发电厂安全生产管理系统 (Plant Safety Management)

> 发电厂日常安全管理 - 隐患排查 → 整改 → 复查 → 闭环

## 业务背景

发电厂日常运行中存在多类型安全风险：电气、压力容器、高处作业、动火、有限空间、危化品等。本系统聚焦最常用的**隐患排查与整改闭环**，按发电厂分区与作业风险分类管理。

## 核心特征

- **发电厂分区**：主厂房 / 锅炉区 / 汽轮机区 / 电气区 / 燃料区 / 化学水 / 除灰除渣 / 脱硫脱硝 / 冷却塔 / 开关站 / 办公区
- **风险分类**：电气安全 / 压力容器 / 危险化学品 / 高处作业 / 有限空间 / 动火作业 / 起重作业 / 辐射防护 / 消防安全 / 机械伤害 / 环境排放
- **整改闭环**：登记 → 责任分派 → 整改 → 复查 → 关闭（或退回）
- **自动超期**：到达整改期限自动标记 OVERDUE
- **多维度统计**：区域分布 / 类别分布 / 趋势 / 整改率

## 技术栈

- **后端**：FastAPI + SQLAlchemy + Pydantic v2 + JWT
- **前端**：React 18 + TypeScript + Ant Design 5 + ECharts + Zustand + Vite

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
python seed_data.py     # 生成演示数据（10 条隐患 + admin 账户）
uvicorn app.main:app --reload --port 8000
```

API 文档：http://localhost:8000/docs

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问：http://localhost:5173

**默认账户**：`admin` / `admin123`

## 数据流程

```
发现隐患 → 登记（区域/类别/等级/责任人/期限）
       ↓
   状态：PENDING / IN_PROGRESS（已分派）
       ↓
责任人提交整改 → RECTIFIED（待复查）
       ↓
安全员复查 → 通过：VERIFIED（关闭）
           → 不通过：IN_PROGRESS（退回）
       ↓
超过期限未关闭 → OVERDUE（自动）
```

## 项目结构

```
plant-safety/
├── backend/
│   ├── app/
│   │   ├── api/             # 路由层（auth/hazards/dashboard）
│   │   ├── models/          # ORM 模型（user/hazard）
│   │   ├── schemas/         # Pydantic 验证
│   │   ├── utils/           # 工具函数
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   └── seed_data.py
└── frontend/
    └── src/
        ├── pages/           # Dashboard / HazardList / LoginPage
        ├── components/      # Layout
        ├── api/             # axios 封装
        ├── stores/          # zustand 认证状态
        └── types/
```

## 路线图

- **v1.0**（当前）：隐患排查闭环 + 仪表盘
- v2.0：两票管理（工作票/操作票）
- v3.0：定期安全检查计划与执行
- v4.0：与设备运维系统联动（隐患转工单）
