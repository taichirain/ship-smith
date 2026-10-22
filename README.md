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
