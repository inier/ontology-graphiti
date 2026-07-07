# OHMO Channels 可视化配置管理 - 设计文档

**日期**：2026-06-22
**状态**：已批准

---

## 1. 概述

### 1.1 功能目标

为 ODAP 平台添加 OHMO Channels（IM 渠道）的可视化配置管理功能，支持工作空间级别的渠道配置、热更新、凭证安全存储。

### 1.2 支持的渠道

全部 10 种 IM 渠道：

| 渠道 | 配置字段 | 说明 |
|------|----------|------|
| Telegram | `token`, `chat_id`, `proxy` | Bot Token |
| Slack | `bot_token`, `app_token`, `signing_secret` | OAuth Tokens |
| Discord | `token` | Bot Token |
| 飞书 (Feishu) | `app_id`, `app_secret`, `encrypt_key`, `verification_token` | 企业应用 |
| 钉钉 (DingTalk) | `client_id`, `client_secret`, `robot_code` | 企业内部应用 |
| Email | `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password`, `from_address` | SMTP 配置 |
| QQ | `token`, `app_id`, `app_secret` | QQ 机器人 |
| Matrix | `homeserver`, `access_token`, `user_id` | Matrix 协议 |
| WhatsApp | `access_token`, `phone_number_id`, `verify_token` | WhatsApp Business |
| Mochat | `endpoint`, `token` | Mochat CRM |

---

## 2. 架构设计

### 2.1 后端模块结构

```
odap/biz/integration/channel_management/
├── api/
│   ├── routes.py          # FastAPI 路由
│   └── schemas.py         # Pydantic 请求/响应模型
├── models/
│   └── channel.py         # ChannelConfig 领域模型
├── impl/
│   └── channel_manager_impl.py  # 渠道管理器实现
├── services/
│   └── channel_service.py # 业务编排层
└── storage/
    ├── __init__.py
    └── sqlite_channel_storage.py  # SQLite 持久化
```

### 2.2 前端模块结构

```
frontend/src/modules/channels/
├── components/
│   ├── ChannelList.tsx        # 渠道列表（折叠面板）
│   ├── ChannelCard.tsx        # 单个渠道卡片
│   ├── ChannelConfigForm.tsx  # 渠道配置表单
│   └── ConnectionStatus.tsx   # 连接状态指示
├── pages/
│   └── ChannelManagementPage.tsx  # 渠道管理页
├── services/
│   └── channelApi.ts          # API 调用
├── stores/
│   └── channelStore.ts        # Zustand 状态
└── index.ts
```

### 2.3 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend                                  │
│  ┌─────────────────┐  ┌──────────────────────────────────────┐  │
│  │ AppRoutes.tsx   │  │ ChannelManagementPage.tsx            │  │
│  │ /settings/      │  │ ┌────────────┐ ┌─────────────────┐   │  │
│  │   channels     │──│ │ChannelList │ │ChannelConfigForm│   │  │
│  └─────────────────┘  │ └────────────┘ └─────────────────┘   │  │
│                       └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Backend API                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ odap/web/app.py                                          │   │
│  │ include_router("/api/channels", channel_management.routes)│   │
│  └──────────────────────────────────────────────────────────┘   │
│                                │                                  │
│                                ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ channel_management/api/routes.py                         │   │
│  │ GET/POST/PUT/DELETE /api/channels/{id}/test/enable/disable │
│  └──────────────────────────────────────────────────────────┘   │
│                                │                                  │
│                                ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ channel_management/services/channel_service.py           │   │
│  │ - 业务逻辑编排                                             │   │
│  │ - 加密/解密凭证                                            │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                │                                  │
│                                ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ channel_management/storage/sqlite_channel_storage.py      │   │
│  │ - SQLite 持久化                                           │   │
│  │ - 加密字段存储                                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ OHMO Integration: ChannelManager                          │   │
│  │ - 动态加载/卸载渠道                                        │   │
│  │ - 订阅配置变更事件                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. API 设计

### 3.1 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/channels` | 获取工作空间的所有渠道配置 |
| POST | `/api/channels` | 创建渠道配置 |
| PUT | `/api/channels/{id}` | 更新渠道配置 |
| DELETE | `/api/channels/{id}` | 删除渠道配置 |
| POST | `/api/channels/{id}/test` | 测试连接 |
| POST | `/api/channels/{id}/enable` | 启用渠道（热更新） |
| POST | `/api/channels/{id}/disable` | 停用渠道（热更新） |

### 3.2 请求/响应模型

**ChannelConfigResponse**（凭证已脱敏）：
```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "channel_type": "feishu",
  "name": "飞书渠道",
  "enabled": false,
  "allow_from": ["*"],
  "config": {
    "app_id": "cli_xxx",
    "has_credential": true,
    "has_encrypt_key": true
  },
  "status": "disconnected",
  "created_at": "2026-06-22T10:00:00Z",
  "updated_at": "2026-06-22T10:00:00Z"
}
```

**CreateChannelRequest**：
```json
{
  "channel_type": "feishu",
  "name": "飞书渠道",
  "workspace_id": "uuid",
  "enabled": false,
  "allow_from": ["*"],
  "config": {
    "app_id": "cli_xxx",
    "app_secret": "encrypted:xxx",
    "encrypt_key": "encrypted:xxx",
    "verification_token": "encrypted:xxx"
  }
}
```

### 3.3 凭证脱敏规则

API 响应中的敏感字段处理：
- `app_secret` → 不返回，只返回 `has_credential: true`
- `encrypt_key` → 不返回，只返回 `has_encrypt_key: true`
- `smtp_password` → 不返回，只返回 `has_password: true`
- `token` → 不返回，只返回 `has_token: true`
- `access_token` → 不返回，只返回 `has_access_token: true`

**AI/Agent 不可读取凭证**：通过 API 层强制过滤，任何通过 Agent/AI 发起的请求，凭证字段始终为空。

---

## 4. 数据模型

### 4.1 SQLite 表结构

```sql
CREATE TABLE channel_configs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    channel_type TEXT NOT NULL,  -- telegram, slack, feishu, etc.
    name TEXT NOT NULL,
    enabled INTEGER DEFAULT 0,
    allow_from TEXT NOT NULL,    -- JSON array as text
    config TEXT NOT NULL,        -- Encrypted JSON
    status TEXT DEFAULT 'disconnected',  -- disconnected, connected, error
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(workspace_id, channel_type, name)
);

CREATE INDEX idx_channel_ws ON channel_configs(workspace_id);
CREATE INDEX idx_channel_type ON channel_configs(channel_type);
```

### 4.2 领域模型

**ChannelConfig** (Pydantic):
```python
class ChannelType(str, Enum):
    TELEGRAM = "telegram"
    SLACK = "slack"
    DISCORD = "discord"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    EMAIL = "email"
    QQ = "qq"
    MATRIX = "matrix"
    WHATSAPP = "whatsapp"
    MOCHAT = "mochat"

class ChannelStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"

class ChannelConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str
    channel_type: ChannelType
    name: str
    enabled: bool = False
    allow_from: list[str] = Field(default_factory=lambda: ["*"])
    config: dict[str, Any]  # 加密存储
    status: ChannelStatus = ChannelStatus.DISCONNECTED
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
```

---

## 5. 安全设计

### 5.1 加密方案

- **算法**：AES-256-GCM
- **密钥管理**：环境变量 `CHANNEL_ENCRYPTION_KEY`
- **密钥长度**：32 字节（256 位）
- **IV 长度**：12 字节（随机生成）
- **Tag 长度**：16 字节

### 5.2 加密存储格式

每条配置 `config` 字段加密后存储为：
```json
{
  "ciphertext": "base64_encoded_encrypted_data",
  "iv": "base64_encoded_iv",
  "tag": "base64_encoded_auth_tag"
}
```

### 5.3 AI/Agent 隔离

通过以下机制保证 AI/Agent 无法读取凭证：

1. **API 层过滤**：响应序列化前强制移除敏感字段
2. **独立 API 端点**：Agent 使用的 `/api/agent/chat` 等端点不返回凭证
3. **审计日志**：记录所有凭证访问（不含实际值）

---

## 6. 热更新机制

### 6.1 架构

```
Config Change Event Flow:
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Admin updates   │───▶│ ChannelService  │───▶│ ChannelManager  │
│ channel config  │    │ (save to DB)    │    │ (OHMO)          │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      ▼
                                              ┌─────────────────┐
                                              │ Enable/Disable  │
                                              │ specific channel│
                                              └─────────────────┘
```

### 6.2 实现

1. `ChannelService` 保存配置后发布事件
2. `ChannelManager`（OHMO）订阅配置变更事件
3. 收到事件后，动态加载/卸载对应渠道
4. 无需重启整个服务

---

## 7. 前端页面设计

### 7.1 页面布局

```
┌────────────────────────────────────────────────────────────────┐
│ 渠道管理                                              [返回设置]  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ [+] 添加渠道                                              │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  ▼ 飞书                                                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ 飞书渠道                              [●] 已断开  [编辑]  │  │
│  │ App ID: cli_xxx                      [测试] [启用]       │  │
│  │ 凭证: 已配置                                           │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  ▼ 钉钉                                                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ 钉钉渠道                              [●] 已连接  [编辑]  │  │
│  │ Client ID: dingxxx                   [测试] [停用]       │  │
│  │ 凭证: 已配置                                           │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  ▼ Telegram (已折叠)                                          │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 7.2 配置表单

每种渠道类型的配置表单根据 `ChannelConfigs` 动态渲染必填字段。

---

## 8. 测试策略

### 8.1 单元测试

- `test_channel_storage.py`: SQLite CRUD + 加密解密
- `test_channel_service.py`: 业务逻辑
- `test_channel_routes.py`: API 端点

### 8.2 集成测试

- 热更新功能测试
- 多工作空间隔离测试

---

## 9. 依赖项

### 9.1 Python 依赖

- `cryptography>=41.0.0` (AES-256-GCM)
- 复用现有 SQLite 存储模式

### 9.2 前端依赖

- 复用现有 Ant Design 6 组件
- 复用现有 Zustand 状态管理

---

## 10. 实施计划

### Phase 1: 基础架构
- 创建后端模块骨架
- 创建前端模块骨架
- SQLite 存储 + 加密基础

### Phase 2: API 开发
- CRUD API 实现
- 凭证加密/解密
- AI/Agent 隔离

### Phase 3: 热更新
- OHMO ChannelManager 集成
- 配置变更事件机制

### Phase 4: 前端 UI
- 渠道列表页面
- 配置表单
- 连接状态展示

### Phase 5: 测试与完善
- 单元测试
- 集成测试
- 文档
