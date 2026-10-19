# Agent 详解

Agent 是运行在目标服务器上的轻量进程，负责执行部署任务、上报状态和同步 Feature Flag。

## 运行原理

Agent 采用 **主动轮询** 模式，而非 Core 主动推送：

```
  Agent                        Core API
   │                             │
   ├─ 每 30s 轮询 ──────────────→│  GET /agents/tasks
   │←───────── 任务（或无任务） ──┤
   │                             │
   ├─ 领取任务 ─────────────────→│  POST /tasks/:id/start
   │←──────── status=running ────┤
   │                             │
   ├─ 执行 git / docker compose   │
   │                             │
   ├─ 增量回传日志 ─────────────→│  POST /tasks/:id/logs
   │                             │
   ├─ 完成任务 ─────────────────→│  POST /tasks/:id/finish
   │←──── status=success/failed ─┤
```

这种设计的优势：
- **无需 SSH**：目标服务器不需要开放入站端口
- **无需 Core 主动连接**：Agent 在 NAT 或防火墙后也能工作
- **天然异步**：Agent 离线不影响 Core 的正常运行

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `SHIPSMITH_CORE_URL` | ✅ | Core API 地址，如 `http://core-host:8000/api/v1` |
| `SHIPSMITH_AGENT_TOKEN` | ✅ | Agent 鉴权 Token（创建项目时获取） |
| `SHIPSMITH_WORKDIR` | ✅ | 部署工作目录，如 `/opt/myapp` |
| `SHIPSMITH_POLL_INTERVAL` | ❌ | 任务轮询间隔（秒），默认 30 |
| `SHIPSMITH_HEARTBEAT_INTERVAL` | ❌ | 心跳间隔（秒），默认 30 |
| `SHIPSMITH_FLAGS_INTERVAL` | ❌ | Flag 同步间隔（秒），默认 30 |

## 安装方式

### 方式 1：一键安装命令（推荐）

在项目接入页点击 **Generate Install Command**，生成包含所有参数的安装命令，在目标服务器执行即可。

**systemd 模式：**

```bash
curl -fsSL https://shipsmith.example.com/install.sh | sh -s -- \
  --project-id <ID> \
  --agent-id <AGENT_ID> \
  --core-url "http://your-core-host:8000/api/v1" \
  --token "<TOKEN>" \
  --workdir "/opt/myapp"
```

脚本会自动：
1. 下载 Agent 二进制
2. 写入 `/etc/shipsmith/env` 配置文件
3. 安装 systemd service
4. 启动 Agent 服务

**Docker 模式：**

```bash
docker run -d --name shipsmith-agent-<ID> \
  --restart always \
  -e SHIPSMITH_CORE_URL="http://your-core-host:8000/api/v1" \
  -e SHIPSMITH_AGENT_TOKEN="<TOKEN>" \
  -e SHIPSMITH_PROJECT_ID=<ID> \
  -e SHIPSMITH_AGENT_ID=<AGENT_ID> \
  -e SHIPSMITH_WORKDIR="/opt/myapp" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /opt/myapp:/opt/myapp \
  shipsmith/agent:latest
```

需要挂载 Docker socket 以便 Agent 在容器内执行 `docker compose` 命令。

### 方式 2：手动安装

接入页提供完整的手动安装步骤，适合无法直接执行安装命令的场景：
- 手动下载 Agent 二进制
- 配置环境变量或 `.env` 文件
- 使用 systemd、supervisor 或 screen 管理进程
- 手动启动 Agent

## 任务生命周期

```
queued → running → success
                  → failed
                  → rolled_back
                  → rollback_failed
```

| 状态 | 说明 |
|------|------|
| `queued` | 任务已创建，等待 Agent 领取 |
| `running` | Agent 已领取并正在执行 |
| `success` | 部署成功 |
| `failed` | 部署失败 |
| `rolled_back` | 回滚成功 |
| `rollback_failed` | 回滚失败 |

**超时机制**：Agent 领取任务后，lease 有效期为 300 秒。Agent 定期发送 heartbeat 续期。如果 Core 未收到 heartbeat，任务自动标记为 `failed`。

## 多目标部署（v0.6+）

一个项目可以绑定多台 Agent（project_targets），一次部署创建多个 DeploymentTarget 记录：

- **all-at-once 模式**：所有目标同时变为 `queued`，各自 Agent 可同时领取
- **rolling 模式**：按 `order_index` 顺序，当前目标成功后推进下一个

Agent 本身不感知多机部署——它只领取属于自己的 `agent_id` 的任务并执行。编排逻辑在 Core 侧完成。

## 心跳与健康

Agent 每 30 秒（可配置）发送心跳到 Core：

```json
{
  "runtime": {
    "os_name": "Ubuntu",
    "shell": "/bin/bash",
    "docker_compose_command": "docker compose"
  },
  "system": {
    "cpu_percent": 45.2,
    "mem_used_mb": 2048,
    "mem_total_mb": 8192,
    "disk_used_percent": 62.1
  },
  "containers": [
    {"service": "app", "status": "running"},
    {"service": "db", "status": "running"}
  ],
  "app_health": {
    "status": "healthy",
    "response_ms": 120,
    "http_status": 200
  },
  "agent_version": "1.0.0"
}
```

Core 根据心跳数据：
- 更新 `project_status` 快照
- 判断 Agent 在线状态（超过 10 分钟无心跳 → agent_offline 告警）
- 记录首次上线时间（`agent_first_seen_at`）
- 跟踪健康状态变化（healthy ↔ degraded ↔ unhealthy）

## 常见排障

| 问题 | 可能原因 | 检查方式 |
|------|---------|---------|
| Agent 未上线 | Core URL 不可达 | 检查网络连通性和防火墙 |
| Token 无效 | token 已 rotate 或错误 | 在项目页重新生成并更新配置 |
| 部署卡住 | 任务 lease 过期 | 等待 5 分钟自动超时，或手动取消 |
| 日志不更新 | Agent 进程异常 | 检查 systemd 状态：`systemctl status shipsmith-agent` |
| Docker 命令失败 | Docker socket 未挂载 | 检查 `/var/run/docker.sock` 是否存在 |
