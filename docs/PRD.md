# ShipSmith MVP 产品技术文档

> 版本：v0.2（MVP）  
> 日期：2026-05-08  
> 定位：给「1人 SaaS 团队」的轻量级部署 + 功能发布控制台

---

## 1. 产品定位

**一句话**：让 1 个人也能安全、可控地部署 SaaS，并用最小心智成本控制功能发布。

### 1.1 目标用户
- 独立开发者 / 1 人技术团队
- 使用单台或少量 Linux 服务器部署 SaaS
- 已使用 GitHub / GitLab + Docker Compose 管理项目
- 不想引入 Kubernetes、ArgoCD、LaunchDarkly 这类偏重方案

### 1.2 MVP 解决的问题
1. 一个项目绑定一个 Git 仓库 + 一个部署目录，支持面板触发部署
2. 提供全局 Feature Flag，30 秒内所有实例感知
3. 提供基础健康面板，看到服务状态、运行版本、最后心跳
4. 记录部署历史和失败日志，便于排查与回滚

### 1.3 MVP 不做这些事
- 不支持 K8s、Swarm、多服务器编排
- 不支持百分比灰度、A/B 测试、用户分群
- 不支持自动扩缩容
- 不替代 CI；测试和镜像构建仍可由 GitHub Actions / GitLab CI 负责
- 不做复杂告警系统（邮件、短信、飞书、PagerDuty 先不做）
- 不做多租户 SaaS 平台；默认自用或单团队使用

---

## 2. 产品原则

### 2.1 设计原则
- **单机优先**：先把单服务器 + Docker Compose 场景做好
- **失败可见**：部署、回滚、同步失败都要有明确状态和日志
- **默认保守**：Feature Flag 默认关闭，异常情况下不自动放量
- **接入简单**：尽量不要求用户开放入站端口或安装复杂依赖
- **控制面统一**：Core 不主动 SSH 到业务机；统一由 Agent 轮询 Core 领取任务

### 2.2 成功标准
- 用户能在 30 分钟内完成一次从接入到首次部署
- 用户能在面板看到最近一次部署是否成功以及失败原因
- 用户能通过一个开关控制 SaaS 代码中的一项新功能开关
- 用户能在服务异常时，从面板快速确认是 Agent 离线、容器异常还是应用健康检查失败

---

## 3. 技术架构

```
┌─────────────────────────────────────────┐
│  ShipSmith Panel (Next.js 15 + shadcn)  │
│  项目 / 部署 / Feature 开关 / Health     │
└──────────────┬──────────────────────────┘
               │ HTTPS
┌──────────────▼──────────────────────────┐
│  ShipSmith Core (Python + FastAPI)      │
│  • 项目与部署 API                        │
│  • 任务队列（部署 / 回滚）                │
│  • Feature Flag 配置中心                 │
│  • 接收 Agent 心跳与日志                  │
│  • PostgreSQL                            │
└──────────────┬──────────────────────────┘
               │ HTTPS 轮询 / 上报
               ▼
┌─────────────────────────────────────────┐
│  ShipSmith Agent (Python)               │
│  • 轮询待执行任务                         │
│  • 执行 git / docker compose             │
│  • 同步 Feature Flag 到本地               │
│  • 采集心跳、健康、容器信息               │
└──────────────┬──────────────────────────┘
               │ 本机调用
               ▼
┌─────────────────────────────────────────┐
│  SaaS Server（被管理机器）               │
│  Docker Compose / Git Working Copy      │
└─────────────────────────────────────────┘
```

### 3.1 为什么选 Agent 轮询
- 不要求业务机器开放 SSH 入站给 Core
- 网络模型更简单，适合云主机 / 家宽 / NAT 环境
- 认证统一为 Agent Token，不需要保存 SSH 私钥
- 后续扩展成长轮询或 WebSocket 也更自然

### 3.2 技术栈
| 层级 | 选型 | 理由 |
|------|------|------|
| 面板 | Next.js 15 + TypeScript + Tailwind + shadcn/ui | 开发快，适合做控制台 |
| 后端 | Python + FastAPI + Pydantic | API 开发快，文档与校验体验成熟，适合控制面 |
| 数据库 | PostgreSQL | 关系数据、审计记录、后续易扩展 |
| Agent | Python | 更贴近运维脚本生态，系统命令编排更自然 |
| SDK | Node.js | 业务应用多数是 Node 场景时接入最顺，先只做本地 flags 读取 |
| 任务分发 | PostgreSQL + 应用层轮询 | MVP 不引入额外消息队列 |

### 3.3 技术方案定稿
- `web`：Next.js，负责控制台 UI
- `api`：FastAPI，负责项目、部署、回滚、flags、heartbeat API
- `agent`：Python，负责执行部署任务、健康检查、日志回传
- `sdk`：Node.js，负责给 SaaS 应用读取本地 flags 文件
- `schema`：Pydantic + OpenAPI，作为 Core、Agent、前端之间的协议边界

---

## 4. 核心流程

### 4.1 部署流程
1. 用户在 Panel 点击「部署」或收到 Webhook 事件
2. Core 创建一条 `deployment` 记录，状态为 `queued`
3. Agent 轮询 `/api/v1/agents/tasks` 领取任务
4. Agent 在本机执行部署命令
5. Agent 持续回传任务进度和日志
6. Agent 完成后回传最终状态、commit hash、容器状态、健康检查结果
7. Core 将部署记录更新为 `success` 或 `failed`

### 4.2 回滚流程
1. 用户在某次历史部署记录上点击「回滚到此版本」
2. Core 创建一个 `rollback` 类型任务，目标指向历史成功部署
3. Agent 拉取任务后切换到目标版本并重新执行 `docker compose up -d`
4. Agent 完成健康检查后回报结果
5. Core 记录一条新的部署记录，状态为 `rolled_back` 或 `rollback_failed`

### 4.3 Feature Flag 同步流程
1. 用户在 Panel 修改开关
2. Core 更新数据库中的 flag 与版本号
3. Agent 每 30 秒拉取一次变更
4. Agent 原子写入本地 flags 文件
5. SaaS 应用通过本地 SDK 读取 flags，30 秒内生效

### 4.4 Health 流程
1. Agent 每 30 秒采集系统资源、容器状态、应用健康检查结果
2. Agent 上报给 Core
3. Core 更新项目当前健康快照，并保留最近一段时间的心跳记录
4. Panel 根据规则展示绿/黄/红状态

---

## 5. 作用域与约束

### 5.1 MVP 支持范围
- 单个 Agent 管理单台 Linux 服务器
- 每个项目对应一个 Git 仓库工作目录
- 通过 `docker compose` 启停项目
- 支持手动部署与基于 Webhook 的自动部署
- 支持全局 Feature Flag
- 支持基础健康看板和部署日志

### 5.2 环境前提
- Linux x86_64 / arm64
- 已安装 `git`、`docker`、`docker compose`
- Agent 运行用户具备目标项目目录读写权限
- Agent 运行用户具备执行 Docker 命令的权限

### 5.3 明确不支持
- Windows / macOS 作为正式被管理节点
- 复杂蓝绿发布、金丝雀发布
- 多活区域、跨机房调度
- 业务级链路追踪、APM、日志检索平台替代

---

## 6. 项目配置规范

项目根目录放置 `shipsmith.yaml`：

```yaml
project: "my-saas"

git:
  repo: "git@github.com:user/my-saas.git"
  branch: "main"

deploy:
  workdir: "/opt/my-saas"
  strategy: "compose-build" # compose-build | compose-pull

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
  install_command: ""
  pre_deploy: ""
  post_deploy: ""
```

### 6.1 字段说明
- `deploy.workdir`：业务项目实际部署目录，Agent 在此目录执行命令
- `deploy.strategy`：
  - `compose-build`：拉代码后本机构建镜像并启动
  - `compose-pull`：拉代码后 `docker compose pull && up -d`
- `flags.file`：按项目隔离的本地 Feature Flag 文件路径
- `runtime.pre_deploy` / `post_deploy`：预留给简单脚本，MVP 可选

### 6.2 MVP 限制
- `shipsmith.yaml` 必须由用户自行维护在仓库中
- Core 不提供在线编辑 `shipsmith.yaml`
- 仅支持一个主服务 `compose.service` 用于健康判定

---

## 7. 部署引擎设计

### 7.1 控制模型
- Core 只负责创建任务、记录状态、展示结果
- Agent 负责实际执行部署命令
- 所有部署、回滚都通过任务表驱动，不直接远程登录业务机器

### 7.2 部署命令模板

#### `compose-build`
```bash
git fetch --all --prune
git checkout <target_commit_or_branch>
git reset --hard <target_commit_or_branch>
docker compose -f <compose_file> build
docker compose -f <compose_file> up -d
```

#### `compose-pull`
```bash
git fetch --all --prune
git checkout <target_commit_or_branch>
git reset --hard <target_commit_or_branch>
docker compose -f <compose_file> pull
docker compose -f <compose_file> up -d
```

### 7.3 部署状态机
`queued -> running -> success | failed`

补充状态：
- `cancelled`：任务被取消，MVP 可仅保留字段，暂不实现取消按钮
- `rolled_back`：一次回滚任务成功完成
- `rollback_failed`：回滚任务执行失败

### 7.4 并发规则
- 同一项目任意时刻只能存在一个 `queued` 或 `running` 任务
- 若用户重复点击部署，返回 409 并提示已有进行中的任务
- Webhook 命中进行中项目时，默认丢弃或标记为 `skipped`

### 7.5 失败判定
- `git fetch` / `checkout` 失败：直接失败
- `docker compose build/pull/up` 任一步失败：直接失败
- 命令成功但健康检查失败：标记为失败
- Agent 在执行中断连超过 2 分钟：标记为失败并附带 `agent_disconnected`

---

## 8. 回滚策略

### 8.1 回滚单元
MVP 的回滚单元定义为：**一个历史成功部署记录对应的 commit hash**。

原因：
- 比单纯 Image ID 更容易和 Git 历史对应
- 更符合独立开发者对“回滚到哪次提交”的心智模型
- 实现成本低于完整部署快照系统

### 8.2 回滚前提
- 只能回滚到历史上 `success` 的部署记录
- 回滚时使用该部署记录中的 `commit_hash`
- 回滚不保证数据库 schema 自动回退；数据库迁移由业务方自行保证向后兼容

### 8.3 回滚限制
- 如果依赖外部镜像标签漂移，回滚结果可能与历史运行状态不完全一致
- 如果 `.env` 已被手工修改，回滚不会自动恢复旧环境变量

### 8.4 UI 文案建议
回滚按钮旁明确提示：
`回滚代码与容器版本，不回滚数据库和环境变量。`

---

## 9. Feature Flag 设计

### 9.1 范围
- 只做项目级全局开关
- 一个 key 只有 `enabled=true/false`
- 不做用户分群、不做百分比灰度

### 9.2 数据同步
- Agent 每 30 秒调用 `/api/v1/flags/sync`
- 请求带上 `project_id`、`agent_id`、`current_version`
- 若无变更，Core 返回 `304-like` 语义结果或 `version unchanged`
- 有变更时返回完整 flag 字典和版本号

### 9.3 本地缓存策略
- Agent 将 flags 写入 `flags.file.tmp`
- 写入成功后原子 `rename` 为正式文件
- SDK 只读取正式文件，避免半截 JSON
- 拉取失败时继续使用上一次缓存
- 文件不存在或解析失败时，SDK 默认返回 `false`

### 9.4 SDK 约束
- 首版只提供 Node.js SDK
- SDK 不依赖网络请求，只读本地文件
- SDK 暴露最小接口：
  - `isEnabled(key)`
  - `getAllFlags()`

### 9.5 审计要求
- 记录谁改了哪个 flag、旧值、新值、修改时间

---

## 10. Health 面板设计

### 10.1 Agent 上报内容
```json
{
  "project_id": 1,
  "agent_id": "agent-uuid",
  "timestamp": "2026-05-08T12:00:00Z",
  "system": {
    "cpu_percent": 12.5,
    "mem_used_mb": 1024,
    "mem_total_mb": 4096,
    "disk_used_percent": 45
  },
  "containers": [
    {
      "service": "app",
      "status": "running",
      "image": "my-saas:abc123",
      "ports": ["3000:3000"],
      "uptime_seconds": 3600,
      "restart_count": 0
    }
  ],
  "app_health": {
    "status": "healthy",
    "response_ms": 45,
    "http_status": 200,
    "version": "abc123"
  }
}
```

### 10.2 状态灯规则
- 绿色：
  - 最近 2 分钟内收到心跳
  - 主服务容器为 `running`
  - 应用健康检查成功
- 黄色：
  - 最近 2 分钟内有心跳
  - 容器运行中，但健康检查超时或失败
  - 或容器在重启中 / 重启次数异常
- 红色：
  - 超过 2 分钟没有心跳
  - 或主服务容器未运行

### 10.3 面板展示
- 项目状态灯
- 当前运行版本（commit hash）
- 最后心跳时间
- 最近一次部署结果
- CPU / 内存 / 磁盘占用
- 主容器状态与 uptime

### 10.4 保留策略
- `project_status` 表保留当前快照
- `heartbeats` 表保留最近 7 天或最近 1000 条

---

## 11. 认证与权限

### 11.1 用户认证
- MVP 默认单用户后台
- 支持本地账号密码登录
- 不做组织、多角色、多租户

### 11.2 Agent 认证
- 每个项目生成一个 `agent_token`
- Agent 所有请求都通过 `Authorization: Bearer <token>` 鉴权
- Token 只允许访问该项目相关的任务、flags、heartbeat 接口

### 11.3 权限边界
- 登录用户可以创建项目、触发部署、回滚、修改 flags
- Agent 不能创建项目、不能修改 flags，只能拉任务和上报状态

### 11.4 Webhook 安全
- GitHub / GitLab webhook 必须校验签名
- 只接受项目配置的目标分支
- 同一 commit 的重复 webhook 默认忽略

---

## 12. 数据模型（PostgreSQL）

```sql
CREATE TABLE projects (
  id SERIAL PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  git_repo TEXT NOT NULL,
  git_branch VARCHAR(64) NOT NULL DEFAULT 'main',
  deploy_workdir TEXT NOT NULL,
  compose_file VARCHAR(256) NOT NULL DEFAULT 'docker-compose.yml',
  compose_service VARCHAR(128) NOT NULL DEFAULT 'app',
  deploy_strategy VARCHAR(32) NOT NULL CHECK (deploy_strategy IN ('compose-build', 'compose-pull')),
  healthcheck_url TEXT,
  healthcheck_timeout_seconds INTEGER NOT NULL DEFAULT 10,
  flags_file_path TEXT NOT NULL,
  agent_id VARCHAR(64) NOT NULL,
  agent_token VARCHAR(256) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE deployments (
  id SERIAL PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  kind VARCHAR(16) NOT NULL CHECK (kind IN ('deploy', 'rollback')),
  status VARCHAR(32) NOT NULL CHECK (
    status IN ('queued', 'running', 'success', 'failed', 'cancelled', 'rolled_back', 'rollback_failed', 'skipped')
  ),
  trigger_source VARCHAR(16) NOT NULL CHECK (trigger_source IN ('manual', 'webhook', 'rollback')),
  commit_hash VARCHAR(40),
  target_deployment_id INTEGER REFERENCES deployments(id),
  log_excerpt TEXT,
  error_code VARCHAR(64),
  triggered_by VARCHAR(64),
  queued_at TIMESTAMP NOT NULL DEFAULT NOW(),
  started_at TIMESTAMP,
  finished_at TIMESTAMP
);

CREATE TABLE deployment_logs (
  id BIGSERIAL PRIMARY KEY,
  deployment_id INTEGER NOT NULL REFERENCES deployments(id),
  seq INTEGER NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE (deployment_id, seq)
);

CREATE TABLE feature_flags (
  id SERIAL PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  key VARCHAR(64) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT false,
  description TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  updated_by VARCHAR(64),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE(project_id, key)
);

CREATE TABLE flag_audits (
  id BIGSERIAL PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  flag_key VARCHAR(64) NOT NULL,
  old_enabled BOOLEAN,
  new_enabled BOOLEAN NOT NULL,
  changed_by VARCHAR(64) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE project_status (
  project_id INTEGER PRIMARY KEY REFERENCES projects(id),
  agent_last_seen_at TIMESTAMP,
  health_status VARCHAR(16) NOT NULL DEFAULT 'unknown',
  current_commit_hash VARCHAR(40),
  last_deployment_id INTEGER REFERENCES deployments(id),
  snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE heartbeats (
  id BIGSERIAL PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  agent_id VARCHAR(64) NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## 13. API 设计（FastAPI + Pydantic）

### 13.1 Panel API
```txt
POST   /api/v1/auth/login
POST   /api/v1/projects
GET    /api/v1/projects
GET    /api/v1/projects/:id
POST   /api/v1/projects/:id/deploy
POST   /api/v1/projects/:id/rollback
GET    /api/v1/projects/:id/deployments
GET    /api/v1/deployments/:id
GET    /api/v1/deployments/:id/logs
GET    /api/v1/projects/:id/flags
POST   /api/v1/projects/:id/flags
PATCH  /api/v1/flags/:id
```

### 13.2 Agent API
```txt
GET    /api/v1/agents/tasks
POST   /api/v1/agents/tasks/:id/start
POST   /api/v1/agents/tasks/:id/logs
POST   /api/v1/agents/tasks/:id/finish
GET    /api/v1/flags/sync
POST   /api/v1/agents/heartbeat
```

### 13.3 Webhook API
```txt
POST   /api/v1/webhooks/github
POST   /api/v1/webhooks/gitlab
```

### 13.4 关键接口行为
- `POST /projects/:id/deploy`
  - 若存在运行中任务，返回 `409 Conflict`
- `GET /agents/tasks`
  - Agent 一次只领取一个任务
- `POST /agents/tasks/:id/logs`
  - 支持增量追加日志
- `GET /flags/sync`
  - 支持按版本返回是否有变更

---

## 14. 失败路径

### 14.1 部署失败
- 原因示例：拉代码失败、镜像构建失败、容器启动失败、健康检查失败
- 处理：
  - 部署记录标记为 `failed`
  - 展示失败阶段与日志摘要
  - 用户可手动重新部署或选择回滚

### 14.2 回滚失败
- 原因示例：目标 commit 不存在、容器启动失败、健康检查失败
- 处理：
  - 状态标记 `rollback_failed`
  - 不自动继续回滚到更早版本

### 14.3 Agent 离线
- 2 分钟无心跳标红
- 有 `queued` 任务但 Agent 长时间未领取时，前端提示 `agent offline or busy`

### 14.4 Flag 同步失败
- Agent 继续使用本地旧缓存
- 面板显示的是 Core 中的最新配置，不保证业务已即时生效

### 14.5 Webhook 异常
- 签名失败直接拒绝
- 非目标分支事件忽略
- 重复 commit 事件记日志但不重复部署

---

## 15. 安装与接入流程

### 15.1 ShipSmith 自身部署
1. 部署 PostgreSQL
2. 部署 `apps/api` 和 `apps/web`
3. 初始化管理员账号
4. 配置域名与 HTTPS

### 15.2 接入一个新项目
1. 在面板创建项目
2. 填写 Git 仓库、分支、部署目录、Compose 文件、健康检查 URL
3. 获取 `agent_id` 和 `agent_token`
4. 在业务服务器安装并启动 Agent
5. 在业务仓库添加 `shipsmith.yaml`
6. 配置 GitHub / GitLab Webhook
7. 执行首次手动部署，确认健康检查和心跳正常

### 15.3 Agent 安装要求
- 推荐以 `systemd` 方式保活
- 运行前校验 `git`、`docker`、`docker compose`
- 首次启动时校验 Core 连通性和 token 有效性

---

## 16. 非功能要求

### 16.1 性能
- Panel 常用页面响应时间 < 1 秒（100 个项目以内）
- Agent 轮询周期默认 30 秒
- 单次部署日志展示支持至少 1 MB 文本

### 16.2 稳定性
- Core 重启后不丢失任务状态
- Agent 重启后可继续拉取新任务
- Core 宕机期间，业务服务保持现状，不受影响

### 16.3 安全
- 所有 API 仅通过 HTTPS 暴露
- 密码和 token 必须加密存储或至少哈希/加密保存
- 日志中避免打印敏感环境变量

### 16.4 可维护性
- Agent 尽量保持单进程、少依赖
- 所有关键操作保留结构化日志

---

## 17. Monorepo 建议

```txt
shipsmith/
├── apps/
│   ├── web/                  # Next.js 控制台
│   └── api/                  # FastAPI Core
├── packages/
│   ├── sdk/                  # Node.js flags SDK
│   ├── agent/                # Agent
│   ├── config/               # 共享 schema / zod
│   └── db/                   # SQL migrations / db client
├── docs/
│   └── PRD.md
├── docker-compose.yml
└── README.md
```

---

## 18. 开发里程碑（4 周 MVP）

| 周次 | 目标 | 交付物 |
|------|------|--------|
| **Week 1** | Core 骨架 + 数据库 | 项目 CRUD、认证、任务表、部署记录表、基础项目状态 |
| **Week 2** | Agent + 部署任务 | Agent 轮询、部署执行、日志回传、回滚能力 |
| **Week 3** | Feature Flag + SDK | flags CRUD、版本同步、原子写本地文件、Node SDK |
| **Week 4** | Panel + Health | 项目列表、部署详情、健康看板、接入文档、自用上线 |

---

## 19. Roadmap（更细版）

### 19.1 Phase 0：先钉协议和配置

这一阶段的目标不是写业务逻辑，而是先把 Core、Agent、项目配置三者之间怎么说话定死。

1. 定义 `shipsmith.yaml` 的 Pydantic Schema
2. 写一份最小可用的 `shipsmith.yaml` 示例
3. 明确字段必填/选填、默认值、枚举值、错误提示
4. 定义部署状态枚举、健康状态枚举、任务类型枚举
5. 定义 Agent 和 Core 的请求/响应模型：
   - `GET /agents/tasks`
   - `POST /agents/tasks/:id/start`
   - `POST /agents/tasks/:id/logs`
   - `POST /agents/tasks/:id/finish`
   - `POST /agents/heartbeat`
   - `GET /flags/sync`

这一阶段产出物：
- `shipsmith.yaml` schema
- `shipsmith.yaml.example`
- API schema 草案
- 状态机枚举清单

### 19.2 这里说的 “先写 schema 和示例” 是什么意思

意思就是先把项目配置文件长什么样写死，而不是先拍脑袋写 API 或 Agent。

原因很实际：
- Agent 要执行什么命令，取决于 `shipsmith.yaml`
- Core 创建项目时要存哪些字段，取决于 `shipsmith.yaml`
- 健康检查、flags 文件路径、部署目录、compose 文件路径，都要先有统一定义

如果这个文件结构没定，后面的数据库、接口、Agent 逻辑都会反复改。

### 19.3 Phase 1：数据库和 Core 骨架

这一阶段先把控制面的“记录能力”搭起来，不急着做完整前端。

1. 建库与 migration
2. 先落以下主表：
   - `projects`
   - `deployments`
   - `deployment_logs`
   - `project_status`
   - `feature_flags`
   - `flag_audits`
   - `heartbeats`
3. 建 `FastAPI` 项目骨架
4. 接 PostgreSQL
5. 完成基础认证：
   - 管理员登录
   - `agent_token` 鉴权
6. 完成第一批接口：
   - `POST /projects`
   - `GET /projects`
   - `GET /projects/:id`
   - `POST /projects/:id/deploy`
   - `GET /projects/:id/deployments`

这一阶段产出物：
- 可运行的 API 服务
- 数据库 migration
- 能创建项目、查看项目、创建部署任务

### 19.4 Phase 2：Agent 最小闭环

这一阶段只追求“能真的跑一次部署”，先不追求功能全。

1. 实现 Agent 启动与配置加载
2. 实现 Agent 鉴权
3. 实现任务轮询
4. 实现 `compose-build` 部署链路：
   - `git fetch`
   - `git checkout`
   - `git reset --hard`
   - `docker compose build`
   - `docker compose up -d`
5. 实现部署日志增量回传
6. 实现部署完成状态回传
7. 实现部署后的健康检查

这一阶段产出物：
- Agent 可在一台 Linux 机器上独立运行
- 面板或 API 能触发一次真实部署
- 部署成功/失败能落库并看到日志

### 19.5 Phase 3：回滚和健康

这一阶段补全最关键的“出事后能处理”能力。

1. 实现回滚任务创建
2. Agent 支持按历史 `commit_hash` 回滚
3. 实现心跳采集：
   - CPU
   - 内存
   - 磁盘
   - 容器状态
4. 实现应用健康检查上报
5. Core 更新 `project_status`
6. 定义红黄绿状态判定逻辑并落地

这一阶段产出物：
- 可回滚到某次历史成功部署
- 可看到最近心跳和当前健康状态

### 19.6 Phase 4：Feature Flag 和 SDK

这一阶段做发布控制，而不是部署控制。

1. 完成 `feature_flags` CRUD
2. 完成 `flag_audits`
3. 实现 `/flags/sync`
4. Agent 实现 flags 拉取与原子写文件
5. 实现 Node.js SDK：
   - `isEnabled(key)`
   - `getAllFlags()`
6. 处理本地文件不存在、JSON 损坏、同步失败的兜底逻辑

这一阶段产出物：
- 面板能改全局开关
- Agent 能同步到本地
- SaaS 代码能读取 flags

### 19.7 Phase 5：Panel 最小可用界面

这一阶段才把“能用的后端能力”包成真正可操作的控制台。

1. 登录页
2. 项目列表页
3. 项目详情页
4. 部署历史页
5. 部署日志页
6. Feature Flag 页面
7. Health 卡片 / 状态页

这一阶段产出物：
- 不依赖 Postman 也能完成主要操作

### 19.8 Phase 6：上线前收尾

1. 写接入文档
2. 写 Agent 安装说明
3. 写 `systemd` 示例
4. 补基础错误提示和空状态
5. 做一次自托管演练：
   - 创建项目
   - 安装 Agent
   - 首次部署
   - 修改 flag
   - 模拟失败
   - 手动回滚

这一阶段产出物：
- 一套从 0 到部署成功的自用闭环

### 19.9 开发顺序建议

如果你是一个人推进，我建议严格按下面顺序做：

1. `shipsmith.yaml` schema + 示例
2. 数据库表 + 状态枚举
3. FastAPI 项目骨架 + 项目接口
4. Agent 轮询 + 部署任务执行
5. 回滚 + 心跳
6. Flags + SDK
7. Next.js 面板

不要倒过来先做前端，不然很容易出现 UI 先行、协议反复改的问题。

---

*这份 v0.2 的目标不是“把未来都设计完”，而是把 MVP 的控制模型、失败路径和数据边界先钉死，避免实现时反复返工。*
