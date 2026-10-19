# 架构说明

## 整体架构

ShipSmith 采用经典的 **控制平面 + Agent** 架构：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Control Plane                                   │
├─────────────────────────────────┬───────────────────────────────────────────┤
│  Web Panel (Next.js)            │  Core API (FastAPI)                      │
│  - 项目管理                      │  - 部署任务管理                          │
│  - 部署触发                      │  - Agent 任务调度                         │
│  - 回滚操作                      │  - Feature Flag 同步                       │
│  - Feature Flag 管理            │  - 健康状态聚合                          │
└─────────────────────────────────┴───────────────────────────────────────────┘
                                          │
                                          │ HTTP (Bearer Token)
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Target Server                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Agent                                                                      │
│  - 轮询任务 (30s)                                                           │
│  - 执行部署 (git + docker compose)                                          │
│  - 心跳上报 (CPU/内存/磁盘)                                                  │
│  - Flag 同步 (JSON 文件)                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**控制平面**（Core API + Web Panel）部署在管理服务器上，**Agent** 部署在每台目标服务器上。两者通过 HTTP 通信，Agent 主动轮询 Core 领取任务。

## 组件说明

### 1. Web Panel (`apps/web`)

基于 **Next.js 14** 的管理界面，提供：
- 仪表盘、项目列表、创建项目
- 项目详情（部署历史、Feature Flag、通知配置）
- 一键部署 / 回滚 / 重试
- Agent 接入引导（一键安装命令）
- 部署日志查看和失败分析

### 2. Core API (`apps/api`)

基于 **FastAPI** 的控制平面，提供两类 API：

- **Panel API**（管理员）：登录、项目 CRUD、部署触发/回滚、Flag CRUD
- **Agent API**（Agent 使用）：任务轮询、日志回传、状态上报、心跳、Flag 同步

### 3. Database (`packages/db`)

基于 **SQLAlchemy** + **Alembic**，主要表结构：

| 表名 | 用途 |
|------|------|
| `users` | 管理员账号 |
| `projects` | 项目配置（含 agent_token_hash） |
| `project_targets` | 多机部署目标（v0.6+） |
| `deployments` | 部署记录 |
| `deployment_targets` | 目标级执行记录 |
| `deployment_logs` | 部署日志（增量追加） |
| `feature_flags` | Feature Flag 键值对 |
| `flag_audits` | Flag 变更审计 |
| `project_status` | 项目当前状态快照 |
| `heartbeats` | Agent 心跳历史 |

### 4. Agent (`packages/agent`)

在目标服务器运行的轻量进程，职责详见 [Agent 详解](./agent.html)。

### 5. SDK (`packages/sdk`)

Node.js Feature Flag SDK，职责详见 [Feature Flag](./feature-flags.html)。

## 数据流

### 部署流程

```
1. 用户点击 Deploy (Web Panel)
        │
        ▼
2. Core API 创建 Deployment + DeploymentTargets
   - all-at-once: 所有目标 queued
   - rolling: 第一个 queued，其余 blocked
        │
        ▼
3. Agent 轮询 GET /agents/tasks → 领取自己的目标任务
        │
        ▼
4. Agent POST /agents/tasks/:id/start → status=running
        │
        ▼
5. Agent 执行: git fetch → checkout → docker compose → healthcheck
        │
        ▼
6. Agent POST /agents/tasks/:id/logs (增量)
        │
        ▼
7. Agent POST /agents/tasks/:id/finish → status=success/failed
   - rolling 模式: 成功后推进下一个 blocked → queued
   - 全部完成: deployment 汇总状态
```

### Feature Flag 同步流程

详见 [Feature Flag](./feature-flags.html)。

## 安全设计

- **JWT 鉴权**：Web Panel 管理员使用 JWT
- **Agent Token**：每个项目独立生成，SHA256 哈希存储，仅创建时明文显示
- **Agent 隔离**：Agent 只能领取属于自己 `agent_id` 的任务
- **Flag 原子写入**：`tmp` → `rename` 避免半写状态
- **SDK 安全兜底**：文件不存在或损坏时返回 `false`
