# 快速入门

本指南将帮助你在 5 分钟内用 Docker Compose 搭建并运行 ShipSmith。

## 前置要求

- **Docker** 24+
- **Docker Compose** v2+

## 步骤 1：启动服务

```bash
cd ship-smith
docker compose up -d
```

Docker Compose 会自动启动三个服务：

| 服务 | 端口 | 说明 |
|------|------|------|
| **PostgreSQL** | `15436` | 数据库 |
| **API** | `8000` | Core API 服务 |
| **Web** | `3000` | Web 管理面板 |

首次启动会自动运行数据库迁移（Alembic），无需手动执行。

## 步骤 2：登录

打开浏览器访问 **http://localhost:3000**，使用默认账号登录：

- **用户名**: `admin`
- **密码**: `admin123`

> ⚠️ 生产环境请务必修改默认密码！

## 步骤 3：创建你的第一个项目

登录后：

1. 点击 **New Project**
2. 填写项目信息：
   - **Project Name**: 项目名称（如 `my-saas`）
   - **Git Repository**: Git 仓库地址（如 `git@github.com:user/my-saas.git`）
   - **Git Branch**: 默认分支（如 `main`）
   - **Deploy Workdir**: Agent 执行命令的目录（如 `/opt/my-saas`）
   - **Flags File Path**: Feature Flag JSON 文件路径（如 `/var/lib/shipsmith/my-saas/flags.json`）
3. 点击 **Create Project**

创建成功后，你会看到 **Agent 接入引导页**，包含一键安装命令和手动安装步骤。

## 步骤 4：安装 Agent（一键安装）

在项目接入页中，点击 **Generate Install Command** 生成安装命令，然后在目标服务器上执行：

### systemd 模式（推荐）

```bash
curl -fsSL https://shipsmith.example.com/install.sh | sh -s -- \
  --project-id <ID> \
  --agent-id <AGENT_ID> \
  --core-url "http://your-core-host:8000/api/v1" \
  --token "<TOKEN>" \
  --workdir "/opt/myapp"
```

### Docker 模式

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

接入页会**自动轮询 Agent 在线状态**，当 Agent 首次心跳到达时，状态会从 `WAITING` 变为 `ONLINE`。

### 离线安装 / 手动安装

如果目标服务器无法直接执行安装命令，可以使用手动安装步骤：
- 下载 Agent 二进制并手动配置环境变量
- 配置 systemd 服务或 supervisor
- 手动启动 Agent

接入页提供完整的手动安装指引。

## 步骤 5：触发第一次部署

在 Web Panel 中：

1. 进入项目详情页
2. 选择部署模式：
   - **All-at-once**: 所有目标机器同时部署（速度优先）
   - **Rolling**: 按顺序逐台部署（稳定性优先）
3. 点击 **Deploy** 按钮
4. Agent 会自动：
   - `git fetch` 最新代码
   - `git checkout` 到指定分支
   - `docker compose build`（或 `pull`）
   - `docker compose up -d`
   - 回传日志和状态

部署详情页会展示每台目标机器的执行状态和日志。

## 多机部署（v0.6+）

一个项目可以绑定多台服务器。在项目设置页的**"部署目标"**区块中：

- 查看已绑定的目标机器列表
- 新增目标：输入 Agent ID 和名称
- 调整顺序（影响 rolling 发布的执行顺序）
- 启用/禁用目标
- 一次部署自动下发到所有启用目标

支持两种发布策略：
- **All-at-once**: 并行部署到所有目标，速度更快
- **Rolling**: 按顺序逐台部署，某一台失败时暂停后续发布

## 下一步

| 了解 [Agent 运行原理](./agent.html)
- 查看 [Feature Flag 使用指南](./feature-flags.html)
- 查看 [API 参考](./api-reference.md) 获取完整 API 列表
- 在项目详情页设置 Webhook，实现 Git push 自动部署
- 配置通知渠道，接收部署和健康状态告警
