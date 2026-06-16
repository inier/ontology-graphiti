# Research: LLM 与 API 密钥配置管理

**Branch**: `006-llm-config-management` | **Date**: 2026-06-14

## R1: 配置热更新机制

**Decision**: 内存缓存 + 观察者通知模式

**Rationale**:
- 项目已有 `ConfigurationComposer` 使用 `threading.RLock` 保护内存配置，天然支持线程安全的热更新
- 不引入消息队列或配置中心（Nacos/Apollo），避免增加运维复杂度
- 配置变更时：写入 SQLite → 更新内存缓存 → 通知订阅者（回调函数）
- 已发出的请求继续使用旧配置完成（请求级快照），新请求读取最新配置

**Alternatives considered**:
- Redis Pub/Sub：需要额外依赖 Redis，而 Redis 在项目中仅作为 Celery broker，非核心依赖
- 文件监听（watchdog）：配置存 SQLite 而非文件，不适用
- 进程间通信（Signal）：多 worker 场景下不可靠

**Implementation**:
```python
class ConfigManager:
    _subscribers: Dict[str, List[Callable]] = {}  # key -> callbacks
    
    def update_config(self, key: str, value: Any):
        old_value = self._cache.get(key)
        self._storage.save_config(key, value)
        self._cache[key] = value
        self._notify_subscribers(key, old_value, value)
    
    def subscribe(self, key: str, callback: Callable):
        self._subscribers.setdefault(key, []).append(callback)
```

## R2: 敏感配置加密方案

**Decision**: AES-256-GCM 对称加密，密钥从环境变量 `CONFIG_ENCRYPTION_KEY` 读取

**Rationale**:
- Python 标准库 `cryptography` 已在项目依赖中（通过 graphiti-core 间接依赖）
- AES-GCM 提供加密+完整性校验，比 AES-CBC 更安全
- 加密密钥从环境变量读取，不硬编码在代码或数据库中
- 首次使用时如果未设置 `CONFIG_ENCRYPTION_KEY`，自动生成并写入 `.env.docker`

**Alternatives considered**:
- Fernet (cryptography.fernet)：更简单但密钥格式固定，不够灵活
- RSA 非对称加密：密钥管理复杂，配置管理场景不需要非对称
- 简单 Base64 编码：不是加密，安全性不足

**Implementation**:
```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, base64

class ConfigEncryption:
    def __init__(self):
        key_b64 = os.getenv("CONFIG_ENCRYPTION_KEY")
        if not key_b64:
            key = AESGCM.generate_key(bit_length=256)
            key_b64 = base64.b64encode(key).decode()
            # 写入 .env.docker
        self._aesgcm = AESGCM(base64.b64decode(key_b64))
    
    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        ct = self._aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ct).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        data = base64.b64decode(ciphertext)
        nonce, ct = data[:12], data[12:]
        return self._aesgcm.decrypt(nonce, ct, None).decode()
```

## R3: 配置统一读取入口 — 消除 15+ 文件分散读取

**Decision**: 扩展 `ConfigurationComposer` 为唯一配置读取入口，添加 L5(DB) 层

**Rationale**:
- 项目已有 `ConfigurationComposer` 5 层配置体系（L0-L4），但未被广泛使用
- 新增 L5(DB) 层：从 SQLite 读取管理员通过界面保存的配置，优先级最高
- 所有模块通过 `composer.get("llm.api_key")` 读取配置，不再直接 `os.getenv()`
- 迁移策略：逐步替换，先替换 LLM 相关的 15+ 处，再替换其他服务配置

**Alternatives considered**:
- 全局单例 SecurityConfig 扩展：已有但仅覆盖安全相关配置，扩展性差
- 环境变量覆盖（写入 os.environ）：副作用大，多 worker 场景不一致
- 配置文件热更新：需要文件监听，且与 SQLite 存储不一致

**Migration plan**:
1. 扩展 `ConfigurationComposer` 新增 L5(DB) 层和缺失的 schema（neo4j.*, minio.*, tavily.* 等）
2. 创建 `get_config()` 全局便捷函数
3. 逐文件替换 `os.getenv("OPENAI_API_KEY")` → `get_config("llm.api_key")`
4. 保持环境变量作为 L1 层的降级方案

## R4: 外部服务连接验证策略

**Decision**: 按服务类型实现轻量级连接测试

**Rationale**:
- 每种外部服务的连接测试方式不同，需要分类实现
- 测试超时设为 10 秒，超时视为不可用
- 测试结果缓存 60 秒，避免频繁测试

**Service-specific test strategies**:

| 服务 | 测试方式 | 超时 |
|------|---------|------|
| LLM (OpenAI 兼容) | POST /v1/chat/completions with minimal prompt | 10s |
| Neo4j | `neo4j` driver verify_connectivity() | 5s |
| MinIO | HEAD /minio/health/live | 5s |
| OPA | GET /v1/policies | 5s |
| Redis | PING command | 3s |
| Tavily | POST /search with test query | 10s |
| DuckDuckGo | GET search with test query | 10s |
| SerpAPI | GET /search with test query | 10s |

**Alternatives considered**:
- 仅验证配置格式（不实际连接）：无法发现密码错误等运行时问题
- 完整功能测试：太重，保存配置时不需要

## R5: 前端配置页面架构

**Decision**: Ant Design 6 分组卡片 + 表单 + 抽屉

**Rationale**:
- 使用 Ant Design 6 的 Collapse + Form 组件实现分组配置展示
- 每个服务类别一个 Collapse.Panel，内含该服务所有配置项的 Form
- 敏感字段使用 Input.Password 组件，支持点击显示
- 连接测试使用 Button + Spin + Tag 展示结果
- 变更历史使用 Drawer + Timeline 组件
- 状态管理使用 Zustand，与项目现有模式一致

**Alternatives considered**:
- Tab 页签切换：服务类别多时 Tab 过于拥挤
- 独立页面：增加路由复杂度，不如单页面分组折叠
- Modal 弹窗编辑：不适合大量配置项的展示

## R6: 配置变更审计

**Decision**: SQLite 表记录变更，与现有审计体系集成

**Rationale**:
- 配置变更是高敏感操作，必须记录完整的变更前后值
- 使用独立的 `config_revisions` 表而非通用审计表，便于查询和回滚
- 同时通过 `unified_audit.py` 写入统一审计日志，满足合规要求
- 回滚通过从 `config_revisions` 读取历史值并重新应用实现

**Alternatives considered**:
- 仅使用 unified_audit：不便于按配置项查询和回滚
- 完整配置快照：存储开销大，配置项之间变更频率差异大
