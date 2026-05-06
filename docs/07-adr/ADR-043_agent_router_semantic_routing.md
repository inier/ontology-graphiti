# ADR-043: Agent Router 语义路由

## 状态
已接受

## 上下文

ODAP 三 Agent 架构（Intelligence / Commander / Operations）需要一个路由层，决定用户请求由哪个 Agent 处理。路由决策的准确性直接影响系统效率和安全：

- **错误路由到 Intelligence**：可能触发不必要的情报分析，浪费 LLM 调用
- **错误路由到 Commander**：可能绕过安全审批，产生未授权的决策
- **错误路由到 Operations**：可能执行不该执行的动作

### 路由方案对比

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A. 规则路由** | 预定义意图→Agent 映射规则 | 确定性高、可审计、零 LLM 成本 | 覆盖不全、维护成本高 |
| **B. LLM 语义路由** | LLM 判断意图后选择 Agent | 灵活、覆盖广 | 不确定、额外 LLM 调用、可被 Prompt 注入攻击 |
| **C. 混合路由** | 规则优先 + LLM 兜底 | 兼顾确定性和灵活性 | 实现稍复杂 |

### 安全约束

- ADR-003/028：所有 Agent 行为需经过 OPA 校验
- Commander Agent 的决策需最高权限验证
- Operations Agent 的执行动作需二次确认

## 决策

**采用方案 C：混合路由 — 规则优先 + LLM 兜底**。

### 路由架构

```
用户请求
    │
    ▼
IntentClassifier.classify()
    │
    ├── 高置信度（> 0.85）──▶ 规则路由表 ──▶ Agent
    │       │                                   │
    │       │  规则示例：                        │
    │       │  "查询"/"分析" → Intelligence      │
    │       │  "决策"/"方案" → Commander          │
    │       │  "执行"/"打击" → Operations         │
    │       │  "什么是" → QAEngine               │
    │
    └── 低置信度（≤ 0.85）──▶ LLM Router ──▶ Agent
            │                                   │
            │  LLM Prompt：                     │
            │  "根据用户意图选择最合适的Agent..."    │
            │                                   │
            ▼                                   │
        仍然不确定 ──▶ Intelligence（最安全默认）  │
                                                │
                                                ▼
                                          OPA 权限校验
                                                │
                                          ┌─────┴─────┐
                                          │ 通过 → 执行 │
                                          │ 拒绝 → 拒绝 │
                                          └───────────┘
```

### 路由规则表

```python
ROUTING_RULES = {
    # 意图关键词 → (Agent, OPA 权限)
    "查询|分析|情报|态势|评估": ("intelligence", "intelligence:query"),
    "决策|方案|推荐|打击|优先": ("commander", "commander:decide"),
    "执行|部署|行动|通知|协调": ("operations", "operations:execute"),
    "什么是|解释|定义|比较": ("qa_engine", "qa:ask"),
    "模拟|推演|what-if|如果": ("simulator", "simulation:run"),
}
```

### Self-Correction 机制

```python
class AgentRouter:
    async def route(self, request: str) -> RoutingResult:
        # 1. 规则匹配
        rule_result = self._match_rules(request)
        if rule_result.confidence > 0.85:
            return rule_result

        # 2. LLM 语义路由
        llm_result = await self._llm_classify(request)
        if llm_result.confidence > 0.7:
            return llm_result

        # 3. 安全默认 → Intelligence（最保守选择）
        return RoutingResult(
            agent="intelligence",
            confidence=0.5,
            reason="low_confidence_default",
            requires_confirmation=True,  # 需人工确认
        )
```

## 后果

### 变得更容易

- **确定性**：85%+ 的请求通过规则路由，可审计、可预测
- **安全性**：低置信度默认路由到 Intelligence（最保守），且需人工确认
- **成本控制**：规则路由零 LLM 调用，仅低置信度请求触发 LLM

### 变得更难

- **规则维护**：新增意图类型需更新路由规则表
- **LLM 路由风险**：Prompt 注入可能导致错误路由，但 OPA 校验是最后防线
- **测试复杂度**：需测试规则路由 + LLM 路由 + 默认路由三条路径

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| Prompt 注入导致错误路由 | OPA 校验作为安全网 + 低置信度需人工确认 |
| 规则覆盖不全 | 定期审查 LLM 兜底路由日志，补充规则 |
| LLM 路由延迟 | 设置超时（2s），超时走默认路由 |

## 可逆性

**高**。路由规则表可动态更新，LLM Router 可替换为更复杂的分类模型。路由逻辑与 Agent 实现解耦，修改路由不影响 Agent。

## 关联

- 关联 ADR-005（分层 Agent 架构）
- 关联 ADR-003/028（OPA 权限校验）
- 关联 M-10 DESIGN.md（Agent 模块）
- 影响 WR-12（Agent Router）
