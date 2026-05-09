# 快速入门

本指南将帮助你在 5 分钟内搭建并运行 ShipSmith。

## 前置要求

- **PostgreSQL** 12+
- **Python** 3.10+
- **Node.js** 18+
- **npm** 或 **yarn**

## 步骤 1：准备数据库

确保 PostgreSQL 已启动，然后创建数据库：

```bash
createdb shipsmith
```

如果你需要自定义连接信息，设置环境变量：

```bash
export DATABASE_URL="postgresql://user:password@host:5432/shipsmith"
```

## 步骤 2：运行数据库迁移

```bash
cd ship-smith
bash dev.sh db-init
```

这将使用 Alembic 创建所有必要的表结构。

## 步骤 3：启动 Core API

```bash
bash dev.sh start-api
```

API 将在 http://localhost:8000 运行。

你可以访问 http://localhost:8000/docs 查看交互式 API 文档（Swagger UI）。

## 步骤 4：启动 Web Panel

打开另一个终端：

```bash
cd ship-smith/apps/web
npm install
npm run dev
```

Web Panel 将在 http://localhost:3000 运行。

## 步骤 5：登录

打开浏览器访问 http://localhost:3000，使用默认账号登录：

- **用户名**: `admin`
- **密码**: `admin123`

> ⚠️ 生产环境请务必修改默认密码！

## 步骤 6：创建你的第一个项目

登录后：

1. 点击 **New Project**
2. 填写项目信息：
   - **Project Name**: 项目名称（如 `my-saas`）
   - **Git Repository**: Git 仓库地址（如 `git@github.com:user/my-saas.git`）
   - **Git Branch**: 默认分支（如 `main`）
   - **Deploy Workdir**: Agent 执行命令的目录（如 `/opt/my-saas`）
   - **Flags File Path**: Feature Flag JSON 文件路径（如 `/var/lib/shipsmith/my-saas/flags.json`）
3. 点击 **Create Project**

> 📋 创建成功后，**请保存显示的 `agent_token`**，这是 Agent 与 Core 通信的凭证，只会显示一次。

## 步骤 7：安装 Agent

在你的目标服务器上安装 Agent。

### 方式 A：从源码运行（开发环境）

```bash
export SHIPSMITH_AGENT_TOKEN="your-agent-token-here"
export SHIPSMITH_CORE_URL="http://your-core-host:8000/api/v1"
export SHIPSMITH_WORKDIR="/opt/my-saas"

cd ship-smith
bash dev.sh start-agent
```

### 方式 B：使用安装脚本（生产环境）

首先在开发机器上打包：

```bash
bash packages/agent/package.sh 1.0.0
```

然后将生成的 tar.gz 复制到目标服务器，解压并安装：

```bash
tar -xzf shipsmith-agent-v1.0.0-linux-x64.tar.gz
cd shipsmith-agent-v1.0.0

bash install.sh \
  --token "your-agent-token-here" \
  --core-url "http://your-core-host:8000/api/v1" \
  --workdir "/opt/my-saas"
```

启动 Agent：

```bash
source ~/.config/shipsmith/env
shipsmith-agent
```

## 步骤 8：触发第一次部署

在 Web Panel 中：

1. 进入项目详情页
2. 点击 **Deploy** 按钮
3. Agent 会自动：
   - `git fetch` 最新代码
   - `git checkout` 到指定分支
   - `docker compose build`（或 `pull`）
   - `docker compose up -d`
   - 回传日志和状态

## 下一步

- 阅读 [架构说明](./architecture.md) 了解系统设计
- 查看 [API 参考](./api-reference.md) 获取完整 API 列表
- 了解如何使用 [Feature Flag SDK](#)
