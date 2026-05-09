# API 参考

## 基础信息

- **Base URL**: `http://localhost:8000/api/v1`
- **认证方式**: Bearer Token
- **API 文档**: `http://localhost:8000/docs` (Swagger UI)

---

## Panel API（管理员使用）

### 1. 认证

#### POST `/auth/login`

OAuth2 密码授权登录。

**Request:**
```
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1Qi...",
  "token_type": "bearer"
}
```

---

### 2. 项目管理

#### GET `/projects`

获取项目列表。

**Response:**
```json
[
  {
    "id": 1,
    "name": "my-saas",
    "git_repo": "git@github.com:user/repo.git",
    "git_branch": "main",
    "deploy_workdir": "/opt/my-saas",
    "deploy_strategy": "compose-build",
    "created_at": "2026-05-08T10:00:00Z",
    "updated_at": "2026-05-08T10:00:00Z"
  }
]
```

#### GET `/projects/{id}`

获取项目详情。

#### POST `/projects`

创建新项目。

**Request:**
```json
{
  "name": "my-saas",
  "git_repo": "git@github.com:user/repo.git",
  "git_branch": "main",
  "deploy_workdir": "/opt/my-saas",
  "flags_file_path": "/var/lib/shipsmith/my-saas/flags.json",
  "deploy_strategy": "compose-build",
  "healthcheck_url": "http://127.0.0.1:3000/api/health"
}
```

**Response:**
```json
{
  "id": 1,
  "name": "my-saas",
  "agent_id": "agent-550e8400e29b",
  "agent_token": "s3cr3t-t0k3n",
  "...": "..."
}
```

> ⚠️ `agent_token` 只会在创建时返回一次，请妥善保存。

---

### 3. 部署管理

#### POST `/projects/{project_id}/deploy`

触发新部署。

**Request:**
```json
{
  "commit_hash": "abc123...",
  "trigger_source": "manual"
}
```

**Response:**
```json
{
  "id": 1,
  "project_id": 1,
  "kind": "deploy",
  "status": "queued",
  "commit_hash": "abc123...",
  "queued_at": "2026-05-08T10:00:00Z"
}
```

#### POST `/projects/{project_id}/rollback`

回滚到历史成功部署。

**Request:**
```json
{
  "target_deployment_id": 5
}
```

#### GET `/projects/{project_id}/deployments`

获取部署历史列表。

#### GET `/deployments/{id}`

获取单个部署详情。

#### GET `/deployments/{id}/logs`

获取部署日志。

**Response:**
```json
[
  {
    "id": 1,
    "deployment_id": 1,
    "seq": 0,
    "phase": "git_fetch",
    "content": "$ git fetch --all --prune",
    "created_at": "2026-05-08T10:00:00Z"
  }
]
```

---

### 4. Feature Flag

#### GET `/projects/{project_id}/flags`

获取项目所有 Flag。

**Response:**
```json
[
  {
    "id": 1,
    "project_id": 1,
    "key": "new_feature",
    "enabled": true,
    "description": "Enable new UI",
    "version": 3,
    "updated_at": "2026-05-08T10:00:00Z"
  }
]
```

#### POST `/projects/{project_id}/flags`

创建新 Flag。

**Request:**
```json
{
  "key": "new_feature",
  "enabled": false,
  "description": "Enable new UI"
}
```

#### PATCH `/flags/{id}`

修改 Flag。

**Request:**
```json
{
  "enabled": true
}
```

> 每次 `enabled` 变更会增加 `version` 并记录审计。

#### GET `/projects/{project_id}/flags/audits`

获取 Flag 变更审计历史。

---

## Agent API（Agent 使用）

所有 Agent API 使用 `agent_token` 进行认证：

```
Authorization: Bearer <agent_token>
```

### GET `/agents/tasks`

轮询待执行任务。

**Response (有任务时):**
```json
{
  "task": {
    "id": 1,
    "project_id": 1,
    "kind": "deploy",
    "commit_hash": "abc123...",
    "deploy_strategy": "compose-build",
    "created_at": "2026-05-08T10:00:00Z"
  },
  "message": "Task available"
}
```

**Response (无任务时):**
```json
{
  "task": null,
  "message": "No pending tasks"
}
```

---

### POST `/agents/tasks/{task_id}/start`

标记任务开始执行。

**Response:**
```json
{
  "ok": true,
  "task_id": 1,
  "status": "running",
  "started_at": "2026-05-08T10:00:00Z"
}
```

---

### POST `/agents/tasks/{task_id}/logs`

增量追加日志。

**Request:**
```json
{
  "phase": "git_fetch",
  "seq": 0,
  "content": "$ git fetch --all --prune"
}
```

> `seq` 用于去重和排序。

---

### POST `/agents/tasks/{task_id}/finish`

标记任务完成。

**Request (成功):**
```json
{
  "status": "success",
  "commit_hash": "abc123..."
}
```

**Request (失败):**
```json
{
  "status": "failed",
  "error_code": "docker_build_failed",
  "error_message": "Docker image build exited with code 1"
}
```

**状态值:**
| 值 | 说明 |
|---|------|
| `success` | 部署成功 |
| `failed` | 部署失败 |
| `rolled_back` | 回滚成功 |
| `rollback_failed` | 回滚失败 |

---

### POST `/agents/heartbeat`

上报心跳和系统状态。

**Request:**
```json
{
  "system": {
    "cpu_percent": 15.2,
    "mem_used_mb": 2048,
    "mem_total_mb": 8192,
    "disk_used_percent": 45.5
  },
  "containers": [
    {
      "service": "app",
      "status": "Up 2 hours",
      "image": "my-app:latest"
    }
  ],
  "app_health": {
    "status": "healthy",
    "response_ms": 45,
    "http_status": 200
  }
}
```

---

### GET `/agents/flags/sync`

同步 Feature Flags（按版本号）。

**Request:**
```
GET /api/v1/agents/flags/sync?current_version=3
```

**Response (无变更):**
```json
{
  "version": 3,
  "flags": null,
  "changed": false
}
```

**Response (有变更):**
```json
{
  "version": 5,
  "flags": {
    "new_feature": true,
    "beta_mode": false
  },
  "changed": true
}
```

---

## 状态枚举

### 部署状态

| 值 | 说明 |
|---|------|
| `queued` | 排队中 |
| `running` | 执行中 |
| `success` | 成功 |
| `failed` | 失败 |
| `cancelled` | 已取消 |
| `rolled_back` | 回滚成功 |
| `rollback_failed` | 回滚失败 |
| `skipped` | 已跳过 |

### 健康状态

| 值 | 说明 |
|---|------|
| `healthy` | 健康（绿色）|
| `degraded` | 降级（黄色）|
| `unhealthy` | 不健康（红色）|
| `unknown` | 未知（灰色）|

### 错误码

| 值 | 说明 |
|---|------|
| `git_fetch_failed` | Git fetch 失败 |
| `git_checkout_failed` | Git checkout 失败 |
| `git_reset_failed` | Git reset 失败 |
| `docker_build_failed` | Docker build 失败 |
| `docker_pull_failed` | Docker pull 失败 |
| `docker_up_failed` | Docker compose up 失败 |
| `health_check_failed` | 健康检查失败 |
| `agent_disconnected` | Agent 断连 |
