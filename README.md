# 隐患不挂账 · 发电厂安全生产管理系统

> 🚨 巡检发现的隐患最怕"挂账"——口头交代一句、写张纸条、Excel 传一手就没人管了。等下次大检查再翻出来，时间过了三个月；等出了事故再翻账本，已经追不回来。

**这套系统把隐患从"发现"到"关闭"绑成一条不能跳步的状态机**：每条隐患都有责任人、整改期限、整改证据、复查记录；到期没整改自动飘红 `OVERDUE`，复查不通过自动退回重整。同时支持接收来自[设备点检系统](https://github.com/nizuowanzhenbang/equipment-inspection)的 `CRITICAL` 缺陷，自动转成重大安全隐患。

> ⚠️ **免责声明**：本系统是 **厂内安全管理工具**，不能替代应急管理部门的法定安全报告，不能作为事故调查的法定证据。

---

## ⚡ 30 秒看明白你能用它做什么

| 你是谁 | 它帮你做什么 |
|---|---|
| 🛡️ 安全员（HSE） | 登记隐患、复查整改、做月度/年度统计报表 |
| 👷 区域班长 | 接到分派 → 安排人 → 上传整改照片 → 提交复查，全程不用纸 |
| 👨‍💼 整改责任人 | App 看待办、拍照传整改证据、追溯历史隐患 |
| 🏢 安全部主任 | 大屏一眼看完今天的超期数、重大隐患分布、整改率 |

---

## ✨ 核心场景

### 🔁 隐患整改闭环：每一步都有人、有时间、有证据
```
登记（PENDING）→ 分派（IN_PROGRESS）→ 整改提交（RECTIFIED）→ 复查（VERIFIED 关闭 / 退回重整）
                                              ↓
                                    超期自动 OVERDUE
```

- **重大隐患** 整改期限 ≤ 14 天，**一般隐患** ≤ 30 天（写死在规则里，不能拍脑袋延期）
- 复查不通过自动退回 `IN_PROGRESS`，重新走一遍
- 隐患编号 `YH-YYYYMMDD-NNNN`，每条都能溯源

### 🌐 覆盖电厂典型作业风险
- **11 个分区**：主厂房 / 锅炉区 / 汽轮机区 / 电气区 / 燃料区 / 化学水 / 除灰除渣 / 脱硫脱硝 / 冷却塔 / 开关站 / 办公区
- **13 类风险**：电气安全 / 压力容器 / 危险化学品 / 高处作业 / 有限空间 / 动火作业 / 起重作业 / 辐射防护 / 消防安全 / 机械伤害 / 环境排放 / 现场环境 / 其他

### 🔌 接收外部系统推送的隐患
设备点检系统巡检发现 `CRITICAL` 缺陷？不需要安全员二次登记，系统直接 POST 过来自动建隐患单：

> 💡 **联动规则**
> - 设备点检里的 `CRITICAL` 缺陷 → 自动建**重大隐患**（14 天整改期）
> - 其他级别 → 自动建**一般隐患**（30 天）
> - 设备编号前缀自动映射到对应电厂分区
> - 走 `X-Integration-Secret` 头部校验 + `external_source+external_no` 幂等

### 📊 多维统计看板
区域分布 / 类别分布 / 月度趋势 / 整改率 / 超期隐患 TOP，安全部例会需要的数据基本都在大屏上。

---

## 🚀 快速开始

```bash
# 后端
cd backend
pip install -r requirements.txt
python seed_data.py                  # 生成演示数据（10 条隐患 + admin 账户）
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

打开 http://localhost:5173 → 用 `admin / admin123` 登录。

> 🔒 生产部署请务必删掉 seed 用户、改强密码。

---

## 🛠️ 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI · SQLAlchemy · Pydantic v2 · JWT |
| 前端 | React 18 · TypeScript · Ant Design 5 · ECharts · Zustand · Vite |
| 数据 | SQLite（开发）/ PostgreSQL（生产） |
| 端口 | 后端 `8000` / 前端 `5173` |

## 📁 目录结构

```
plant-safety/
├── backend/
│   ├── app/
│   │   ├── api/             # auth / hazards / integration / dashboard
│   │   ├── models/          # user / hazard
│   │   ├── schemas/         # Pydantic 验证
│   │   ├── utils/
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

---

## 🔗 智慧发电厂全家桶中的位置

本项目是 [smart-power-plant](https://github.com/nizuowanzhenbang/smart-power-plant) 七大子系统中的"安全生产"模块。当前已联动：

| 系统 | 关系 |
|---|---|
| [equipment-inspection](https://github.com/nizuowanzhenbang/equipment-inspection) | 推送 `CRITICAL` 缺陷自动建重大隐患 |
| [emission-monitoring](https://github.com/nizuowanzhenbang/emission-monitoring) | v2 规划：严重超标告警 → 推送环保隐患 |

---

## 🚧 路线图

- ✅ **v1.0**：隐患排查闭环 + 仪表盘
- ✅ **v1.1**：与 equipment-inspection 联动接收 `CRITICAL` 缺陷
- 🚧 **v2.0**：两票管理（工作票 / 操作票）+ 角色权限拦截 + WebSocket 实时推送
- 📋 **v3.0**：定期安全检查计划与执行
- 📋 **v4.0**：与更多兄弟系统的隐患联动

## 📜 License

私有项目，未开源。
