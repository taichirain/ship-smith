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

## 组件说明

### 1. Web Panel (`apps/web`)

基于 **Next.js 14** 的管理界面，提供：

- **项目列表页**：查看所有项目，创建新项目
- **项目详情页**：
  - 部署历史列表
  - 一键部署 / 回滚
  - Feature Flag 开关
- **部署详情页**：查看部署日志

### 2. Core API (`apps/api`)

基于 **FastAPI** 的控制平面，提供两类 API：

- **Panel API**（管理员使用）：
  - 登录认证
  - 项目 CRUD
  - 部署触发/回滚
  - Flag CRUD

- **Agent API**（Agent 使用）：
  - 任务轮询
  - 日志回传
  - 状态上报
  - 心跳
  - Flag 同步

### 3. Database (`packages/db`)

基于 **SQLAlchemy** 和 **Alembic**，包含 8 张表：

| 表名 | 用途 |
|------|------|
| `users` | 管理员账号 |
| `projects` | 项目配置（含 agent_token_hash） |
| `deployments` | 部署记录 |
| `deployment_logs` | 部署日志（增量追加） |
| `feature_flags` | Feature Flag 键值对 |
| `flag_audits` | Flag 变更审计 |
| `project_status` | 项目当前状态快照 |
| `heartbeats` | Agent 心跳历史 |

### 4. Agent (`packages/agent`)

在目标服务器运行的轻量 Python 进程，职责：

1. **任务轮询**：每 30 秒检查是否有新任务
2. **部署执行**：
   - `git fetch --all --prune`
   - `git checkout` → `git reset --hard`
   - `pre_deploy` 命令（可选）
   - `docker compose build/pull`
   - `docker compose up -d`
   - `post_deploy` 命令（可选）
3. **日志回传**：每步命令输出通过 `seq` 序号增量上传
4. **心跳上报**：采集 CPU、内存、磁盘、容器状态
5. **Flag 同步**：定期检查并更新本地 `flags.json`

### 5. SDK (`packages/sdk`)

Node.js Feature Flag SDK，职责：

- 从本地 JSON 文件读取 flags
- 基于文件 mtime + TTL 缓存
- 提供 `isEnabled(key)` 和 `getAllFlags()` API
- 文件不存在时返回 `false`（安全兜底）

## 数据流

### 部署流程

```
1. 用户点击 Deploy (Web Panel)
        │
        ▼
2. Core API 创建 Deployment (status=queued)
        │
        ▼
3. Agent 轮询 GET /api/v1/agents/tasks
        │
        ▼
4. Agent POST /api/v1/agents/tasks/:id/start
   Deployment → status=running
        │
        ▼
5. Agent 执行 git fetch / checkout / docker compose ...
        │
        ▼
6. Agent POST /api/v1/agents/tasks/:id/logs (增量)
        │
        ▼
7. Agent POST /api/v1/agents/tasks/:id/finish
   Deployment → status=success/failed
        │
        ▼
8. project_status 快照更新
```

### Feature Flag 同步流程

```
1. 用户在 Panel 切换 Flag
        │
        ▼
2. Core API:
   - 更新 feature_flags 表
   - flag.version += 1
   - 记录 flag_audits
        │
        ▼
3. Agent 轮询 GET /api/v1/agents/flags/sync?current_version=N
        │
        ▼
4. 若版本 > N：返回新 flags
        │
        ▼
5. Agent: tmp → rename 原子写入 flags.json
        │
        ▼
6. 应用 SDK 读取 flags.json（基于 mtime 缓存）
```

## 安全设计

- **JWT 鉴权**：Web Panel 和 Admin 用户使用 JWT
- **Agent Token**：每个项目独立生成，SHA256 哈希存储
- **Flag 原子写入**：`tmp` → `rename` 避免半写状态
- **SDK 安全兜底**：文件不存在或损坏时返回 `false`

## 配置文件

### shipsmith.yaml

项目配置文件（用于手动配置 Agent）：

```yaml
project: "my-saas"

git:
  repo: "git@github.com:user/my-saas.git"
  branch: "main"

deploy:
  workdir: "/opt/my-saas"
  strategy: "compose-build"

compose:
  file: "docker-compose.yml"
  service: "app"

health_check:
  type: "http"
  url: "http://127.0.0.1:3000/api/health"
  timeout_seconds: 10
  expected_status: 200

flags:
  file: "/var/lib/shipsmith/my-saas/flags.json"

runtime:
  env_file: ".env"
  pre_deploy: ""
  post_deploy: ""
```

### Agent 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `SHIPSMITH_CORE_URL` | ✅ | Core API 地址 |
| `SHIPSMITH_AGENT_TOKEN` | ✅ | Agent 鉴权 Token |
| `SHIPSMITH_WORKDIR` | ✅ | 部署工作目录 |
| `SHIPSMITH_POLL_INTERVAL` | ❌ | 任务轮询间隔（秒），默认 30 |
| `SHIPSMITH_HEARTBEAT_INTERVAL` | ❌ | 心跳间隔（秒），默认 30 |
| `SHIPSMITH_FLAGS_INTERVAL` | ❌ | Flag 同步间隔（秒），默认 30 |
