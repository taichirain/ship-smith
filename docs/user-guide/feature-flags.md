# Feature Flag

Feature Flag 是 ShipSmith 的核心功能之一，允许你在运行时动态开关功能，无需重新部署。

## 工作原理

```
  Web Panel 用户切换 Flag
        │
        ▼
  Core API → 更新 feature_flags 表
           → flag.version += 1
           → 记录 flag_audits
        │
        ▼
  Agent 轮询 GET /flags/sync?current_version=N
        │
        ▼
  版本变化 → 原子写入 flags.json
        │
        ▼
  应用 SDK 读取 flags.json（mtime 缓存）
```

## 创建和管理 Flag

在项目详情页的 **Feature Flags** 区块中：

1. **创建 Flag**：点击 **New Flag**，输入 key（如 `new-checkout-flow`）
2. **启用/禁用**：点击开关即时切换，所有 Agent 在下一个 Poll 周期（30 秒内）同步
3. **归档 Flag**：不再使用的 Flag 可以归档，不会影响生产，但不再出现在列表中
4. **审计日志**：每次开关变更记录操作人和时间

## Flag 文件格式

Agent 在目标服务器上维护一个 JSON 文件（路径在项目创建时指定）：

```json
{
  "version": 3,
  "updated_at": "2026-05-09T12:00:00Z",
  "flags": {
    "new-checkout-flow": true,
    "dark-mode": false,
    "payment-v2": true
  }
}
```

写入策略：先写入 `.tmp` 文件，再 `rename` 到目标路径，确保读取时不会遇到半写状态。

## SDK 集成

ShipSmith 提供 Node.js SDK，用于在应用中读取 Flag：

### 安装

```bash
npm install @shipsmith/sdk
```

### 初始化

```typescript
import { createFlagClient } from '@shipsmith/sdk';

const client = createFlagClient({
  flagsFilePath: '/var/lib/shipsmith/myapp/flags.json',
  ttlMs: 5000,  // 缓存有效期 5 秒
});
```

### 使用

```typescript
// 检查某个 Flag 是否启用
if (client.isEnabled('new-checkout-flow')) {
  // 展示新版结账页面
} else {
  // 展示旧版结账页面
}

// 获取所有 Flag
const allFlags = client.getAllFlags();
// { "new-checkout-flow": true, "dark-mode": false, ... }

// 手动刷新
await client.refresh();
```

### 缓存策略

- **基于 mtime**：首次读取后缓存文件 mtime，后续检查 mtime 是否变化
- **TTL 控制**：通过 `ttlMs` 参数控制最大缓存时间（默认 5000ms）
- **安全兜底**：文件不存在或解析失败时所有 Flag 返回 `false`

### 完整示例

```typescript
import { createFlagClient } from '@shipsmith/sdk';
import express from 'express';

const app = express();
const flags = createFlagClient({
  flagsFilePath: '/var/lib/shipsmith/myapp/flags.json',
});

// 中间件：每次请求刷新 Flag
app.use(async (req, res, next) => {
  await flags.refresh();
  // 将 Flag 客户端注入请求对象
  req.flags = flags;
  next();
});

// 路由中使用 Flag
app.get('/api/checkout', (req, res) => {
  if (req.flags.isEnabled('new-checkout-flow')) {
    res.json({ version: 'v2', features: ['express-checkout'] });
  } else {
    res.json({ version: 'v1' });
  }
});

app.listen(3000);
```

## 最佳实践

### 1. 渐进式发布

先在小范围启用新功能，确认稳定后再全量开放：

```
阶段 1: Flag 关闭 → 旧代码运行
阶段 2: Flag 开启 10% → 观察日志和错误
阶段 3: Flag 开启 50% → 继续观察
阶段 4: Flag 全量开启 → 稳定后移除旧代码
```

### 2. 命名规范

- 使用 `kebab-case`：`new-checkout-flow`
- 命名体现功能，而非版本：`use-new-api` 优于 `api-v2`
- 考虑删除时机：可以备注 `remove-after: 2026-06` 在项目 runbook 中

### 3. 安全策略

- Flag 默认关闭（`false`），新功能需要显式开启
- 生产环境 Flag 变更后，Agent 最多 30 秒同步到目标服务器
- 过期的 Flag 及时归档，避免代码中遗留无用判断

### 4. 应用层建议

- **不要**将 Flag 用于安全鉴权（用户权限应走独立系统）
- **不要**在 Flag 中存储敏感信息
- **适合**的功能：UI 改版、支付流程切换、新算法上线
- **不适合**的功能：数据库迁移、基础设施变更
