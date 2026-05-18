# 任务跟踪

## v1.0（已完成）

### 后端
- [x] User / Hazard 模型
- [x] 区域 + 类别 + 等级 + 状态 枚举（发电厂特色字段）
- [x] JWT 登录 + me 接口
- [x] 隐患 CRUD（list/get/create/update）
- [x] 整改提交（rectify）+ 复查（verify）状态流转
- [x] Dashboard：overview / by-area / by-category / trend
- [x] 自动超期标记（每次访问 overview 时刷新）
- [x] seed_data 演示数据生成器

### 前端
- [x] 登录页 + JWT 持久化（zustand + localStorage）
- [x] 主布局（侧边栏 + Header）
- [x] Dashboard：4 KPI + 整改率进度条 + 区域饼图 + 类别柱图 + 趋势堆叠柱图
- [x] HazardList：分页表格 + 多维筛选 + 详情抽屉 + 登记/整改/复查表单

### 文档
- [x] README.md
- [x] CLAUDE.md
- [x] TASK.md

## v2.0（规划）

### 后端
- [ ] 两票管理：工作票 / 操作票 模型
- [ ] 多级审批流（draft → submitted → approved → in_execution → closed）
- [ ] 监护人签字时间戳
- [ ] 安全检查模块（计划 + 执行 + 检查项检查结果 + 自动生成隐患）
- [ ] WebSocket 实时推送重大隐患/超期通知
- [ ] 角色权限拦截装饰器（按 UserRole 校验）

### 前端
- [ ] 两票管理页面
- [ ] 安全检查页面
- [ ] 隐患详情新增整改历史时间线
- [ ] 实时通知 toast

## v3.0（规划）

- [ ] 移动端 H5 优化（现场扫码登记）
- [ ] 隐患照片真实上传 + 缩略图
- [ ] 月度/年度安全报告导出（PDF）
- [ ] 与外部系统集成（设备运维 - 隐患转工单 / 煤质/运输 - 反复预警转隐患）

## 已知问题

- 自动超期触发依赖 overview API 被访问，建议 v2 加定时任务
- 隐患删除接口未实现（业务上需要保留审计记录，故未提供）
- 前端 useEffect 依赖未列 load 全部内部依赖（filters/pageSize）— 简化处理，已用闭包捕获
