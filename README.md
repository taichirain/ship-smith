# ShipSmith

部署自动化 + Feature Flag 控制平面。

## 简介

ShipSmith 是一个轻量级的部署自动化和 Feature Flag 管理工具。

- **一键部署**：从 Git 仓库自动部署到你的服务器
- **即时回滚**：一键回滚到任意历史成功版本
- **Feature Flag**：控制功能开关，无需重新部署
- **Agent 架构**：轻量 Agent 在目标服务器运行，与控制平面解耦

## 架构

```
┌─────────────────────────────────────────────────────────┐
│  Web Panel (Next.js)     │     Admin User           │
└──────────────┬──────────────┴────────────────────────┘
               │ HTTP /api/*
               ▼
┌─────────────────────────────────────────────────────────┐
│  Core API (FastAPI)    │     Control Plane     │
│  + PostgreSQL              │     (Port 8000)        │
└──────────────┬──────────────┴────────────────────────┘
               │
         ┌─────┼─────┐
         ▼     ▼     ▼
      ┌─────┐ ┌─────┐ ┌─────┐
      │Agent│ │Agent│ │Agent│   目标服务器
      │ #1  │ │ #2  │ │ #n  │
      └─────┘ └─────┘ └─────┘
```

## 快速开始

### 1. 启动数据库

确保 PostgreSQL 运行在 localhost:5432，创建数据库：

```bash
createdb shipsmith
```

### 2. 运行 migration

```bash
bash dev.sh db-init
```

### 3. 启动 Core API

```bash
bash dev.sh start-api
```

API 文档: http://localhost:8000/docs

### 4. 启动 Web Panel

```bash
cd apps/web
npm install
npm run dev
```

访问: http://localhost:3000

默认账号: `admin` / `admin123`

## 单机多项目（P0 推荐用法）

同一台机器上跑多个项目时，**一个项目一个独立 Agent 实例**。实例之间使用不同的
token、配置目录、二进制文件名和 systemd 服务名，互不覆盖：

```bash
bash packages/agent/install.sh \
  --instance alpha-forge \
  --token "$AGENT_TOKEN" \
  --core-url "https://shipsmith.example.com/api/v1" \
  --workdir /srv/shipsmith/alpha-forge
```

- 默认配置目录：`/etc/shipsmith/<instance>`（非 root 为 `~/.config/shipsmith/<instance>`）
- 默认服务名：`shipsmith-agent-<instance>.service`
- 重复安装会被拒绝；`--force` 只替换指定实例，不影响其他项目
- 部署目录会写入 `.shipsmith/project.json` 归属标记
- 工作目录有本地改动、不是 ShipSmith 管理的目录、或 remote 不匹配时，部署会被拒绝
- 部署命令有超时和逐行日志；Git 凭据、token 等敏感串会从日志中脱敏

P0 的范围是“单机多项目”；多目标/多服务器编排暂未启用。

## 构建后迁移与 Compose profiles（Phase 2.5）

项目可以通过 API 配置：

- `migration_service`：执行迁移的 Compose 服务，例如 `api`
- `migration_command`：迁移命令，按 argv 拆分执行，例如 `alembic upgrade head`
- `migration_timeout_seconds`：迁移超时，默认 600 秒
- `migration_no_deps`：默认 `true`，迁移容器不自动拉起依赖服务
- `compose_profiles`：显式启用的 Compose profiles，例如 `["data-sync"]` 或 `["sync"]`
- `healthcheck_url` / `healthcheck_expected_status`：建议指向 `/ready`，默认期望 200

部署顺序变为：

```text
pre_deploy（构建前，可选）
→ build / pull
→ migration（构建后、启动前，可选）
→ up -d
→ post_deploy
→ /ready 健康检查
```

迁移失败时不会执行 `up`，旧容器保持不变，部署记录标记 `failure_phase="migration"`。迁移命令走 `docker compose run --rm --no-deps <service> <argv...>`，不经过 shell；需要管道或重定向时请用 pre/post hook。同一个工作目录的部署有文件锁，避免并发迁移；如果多个项目共享同一个数据库，迁移命令自身仍需使用数据库级 advisory lock，ShipSmith 只能保证同一工作目录不并发。

Panel 的创建项目表单（高级表单和向导）已支持配置 `migration_service`、`migration_command`、`migration_timeout_seconds`、`migration_no_deps`、`compose_profiles` 和 `healthcheck_expected_status`。

## 构建超时与缓存

依赖下载较慢的环境（比如镜像源不稳定）常见“构建超时”。现在可以在项目配置中调整：

- `build_timeout_seconds`：`docker compose build` 超时，默认 1800 秒，可调大到 10800
- `pull_timeout_seconds`：`docker compose pull` 超时，默认 900 秒
- `build_no_cache`：默认 `false`（使用 Docker 层缓存）；设为 `true` 时构建加 `--no-cache`

说明：ShipSmith 的“通用缓存”默认就是 Docker 的层缓存——同一台机器上不改 Dockerfile 的部分会复用层，第二次构建通常很快。更细粒度的依赖缓存（如 pip/npm 的 cache mount）需要项目在自己的 Dockerfile 里使用 `RUN --mount=type=cache,...`，ShipSmith 无法替你注入。构建慢的根源通常是网络，生产上建议给构建环境配可用的代理或镜像源。

注意：ShipSmith 只负责执行配置好的迁移命令，不决定 DDL 归属。Forge 的 `migration_command` 只应包含 Forge 自己的 schema 变更；行情表后续 DDL 由 alpha-market-data 维护，不要把它加进 Forge 的 Alembic。

## 健康检查与离线告警（Phase 3）

Agent 会从 Core 拉取项目的健康检查配置，并在每次心跳时检查 `healthcheck_url`：

- `healthcheck_expected_status` 默认 200，适合 `/ready`
- 部署执行期间上报 `unknown`，避免把部署重启误判为故障
- 应用健康状态随心跳写入 `project_status`，并保留在 heartbeat 历史里

服务端会周期性扫描 Agent 最后心跳时间：

- `AGENT_OFFLINE_THRESHOLD_SECONDS`：离线阈值，默认 600 秒
- `AGENT_MONITOR_INTERVAL_SECONDS`：扫描间隔，默认 60 秒
- `HEALTH_MONITOR_ENABLED`：是否启动后台扫描，默认 true

超过阈值会创建/更新 `agent_offline` 告警并发送通知；Agent 恢复心跳后自动 resolved，并发送恢复通知。应用健康从 `unhealthy` 恢复为 `healthy` 时也会 resolved 对应的健康告警。

当前后台扫描按单个 API 进程设计；如果以后跑多个 API worker，需要给扫描器加数据库 advisory lock，避免重复扫描。

## 生产部署与恢复

- 生产 Compose：[`docker-compose.prod.yml`](docker-compose.prod.yml)
- 生产环境变量模板：[`.env.production.example`](.env.production.example)
- 操作手册：[`docs/production.md`](docs/production.md)
- 备份：`scripts/backup_shipsmith.sh`
- 备份恢复校验：`scripts/verify_shipsmith_backup.sh <backup-dir>`

生产模式会拒绝默认口令、短密钥、`CORS_ORIGINS=*` 和非 HTTPS 的 `PUBLIC_CORE_URL`。API/web 只绑定 `127.0.0.1`，TLS 由前置反向代理终止。

Agent 在 Core 不可达时会把部署结果和日志写入 `~/.local/state/shipsmith/outbox/<workdir-hash>/`，每 10 秒重试；Core 恢复后自动补发，不会把已完成的部署丢成失败。

## 按项目停止/启动服务

项目详情页提供 **Stop / Start** 按钮：

- **Stop** 对明确配置的服务执行 `docker compose stop`，只停容器，**不删除容器和卷**。
- **Start** 对同一服务列表执行 `docker compose up -d --no-deps`，并重新跑健康检查。
- 停止后项目进入“有意停止”状态：Agent 心跳上报 `stopped`，期间不产生健康告警；Agent 重启后状态不丢。
- 成功的部署/回滚会自动清除“有意停止”状态。
- 停止/启动都会记录为任务（含日志），在时间线里显示为 `operation_*` 事件。

Stop/Start 需要项目当前没有进行中的部署或其他操作；有正在执行的任务时会返回 409。

## 操作范围与数据库保护

`compose_service` 仅用于主服务/健康检查，不能代表整个项目。项目通过
`app_services` 明确列出参与普通部署、Stop、Start 的服务：

- `service_scope: "app"`（默认）→ 仅操作 `app_services`；启动使用 `--no-deps`，不会隐式启动未列出的依赖。多容器项目必须列全 Web/API/Worker/Beat 等应用服务。
- `service_scope: "all"` → 普通部署和 Stop/Start 均作用于整份 Compose（含数据库），仅用于确实需要整栈生命周期的项目。

首次创建有状态服务与后续数据库升级是独立维护操作，不能依赖普通应用部署隐式完成。升级前应先检查并补全从旧版本迁移来的 `app_services` 配置。

## 目录结构

```
shipsmith/
├── apps/
│   ├── web/          # Next.js 管理面板
│   └── api/          # FastAPI Core API
├── packages/
│   ├── config/        # 共享配置和协议定义
│   ├── db/            # 数据库模型和 migrations
│   ├── agent/         # 部署 Agent
│   └── sdk/           # Node.js Feature Flag SDK
├── docs/
│   ├── PRD.md
│   └── user-guide/   # 用户手册
└── dev.sh             # 开发脚本
```

## 功能清单

- [x] Phase 0: 协议和配置
- [x] Phase 1: 数据库和 Core 骨架
- [x] Phase 2: Agent 最小闭环
- [x] Phase 3: 回滚和健康
- [x] Phase 4: Feature Flag 和 SDK
- [x] Phase 5: Panel 最小可用界面
- [x] Phase 6: Agent 打包分发

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接字符串 | `postgresql://postgres:postgres@localhost:5432/shipsmith` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | `change-me-in-production-please` |
| `ADMIN_USERNAME` | 管理员用户名 | `admin` |
| `ADMIN_PASSWORD` | 管理员密码 | `admin123` |

## 开发

```bash
# 同时启动 API 和 Web
bash dev.sh all

# 打包 Agent 二进制
bash dev.sh package-agent 1.0.0
```

## License

MIT
