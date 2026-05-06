# ADR-003: OPA 策略治理引擎（MVP + 生产化）

> **来源**: `docs/ARCHITECTURE.md` 第 17 章

---


**状态**: 已接受

**上下文**: 系统需要完整的策略治理能力，支持高危操作校验、细粒度权限控制、策略可视化管理和热更新。

**决策**: OPA 作为统一策略引擎，覆盖所有策略场景，采用 MVP 快速验证 + 生产化平滑演进策略。

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         OPA 策略治理架构                                   │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  策略管理接口层（AdminConsole）                                       │ │
│  ├─────────────────────────────────────────────────────────────────────┤ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │ │
│  │  │ Markdown 编辑 │  │  可视化编辑器 │  │   策略测试   │              │ │
│  │  │  (SKILL.md)  │  │  (图形化)     │  │   (在线 REPL)│              │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                              ↓                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  策略转换引擎                                                         │ │
│  ├─────────────────────────────────────────────────────────────────────┤ │
│  │  ┌─────────────────────────────────────────────────────────────┐   │ │
│  │  │  Markdown (.md)  ───→  JSON Schema  ───→  Rego (.rego)    │   │ │
│  │  │                                                              │   │ │
│  │  │  ## 策略名称                                                   │   │ │
│  │  │  ### 条件                                                     │   │ │
│  │  │  - user.role == "admin"                                      │   │ │
│  │  │  ### 操作                                                      │   │ │
│  │  │  - allow: true                                               │   │ │
│  │  │                                                              │   │ │
│  │  │  ↓ 转换                                                       │   │ │
│  │  │                                                              │   │ │
│  │  │  package policy.admin                                         │   │ │
│  │  │  allow { input.user.role == "admin" }                        │   │ │
│  │  └─────────────────────────────────────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                              ↓                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  OPA Bundle 服务                                                   │ │
│  ├─────────────────────────────────────────────────────────────────────┤ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │ │
│  │  │   Bundle   │  │   Version   │  │   Cache    │                  │ │
│  │  │   Server   │  │  Manager    │  │  Manager   │                  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │ │
│  │         ↓                ↓                ↓                           │ │
│  │  ┌─────────────────────────────────────────────────────────────┐   │ │
│  │  │  OPA Server (Docker)                                       │   │ │
│  │  │  • /v1/policies      • /v1/data       • /v1/compile        │   │ │
│  │  └─────────────────────────────────────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                              ↓                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  策略覆盖场景                                                        │ │
│  ├─────────────────────────────────────────────────────────────────────┤ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │ │
│  │  │   身份权限  │  │   Skill    │  │   本体     │                  │ │
│  │  │  (RBAC)    │  │  (细粒度)  │  │  (节点)    │                  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │ │
│  │  │   数据权限  │  │   API 权限  │  │   UI 权限  │                  │ │
│  │  │ (工作空间)  │  │  (网关)     │  │  (界面)    │                  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

## 1. Markdown 策略格式规范

```markdown
# SKILL-permission.md - Skill 执行权限策略
# 元数据
name: skill_permission
version: 1.0.0
description:
  zh: Skill 执行权限控制
  en: Skill Execution Permission Control
scope: workspace  # global | workspace

# 策略规则
rules:
  - id: admin_full_access
    condition: user.role == "admin"
    effect: allow
    priority: 100

  - id: editor_skill_access
    condition: user.role == "editor" and skill.category in ["intelligence", "analysis"]
    effect: allow
    priority: 50

  - id: viewer_readonly
    condition: user.role == "viewer"
    effect: allow
    conditions:
      - skill.mode == "read"
    effect_conditions:
      - not skill.mode in ["write", "execute"]

  - id: skill_disabled
    condition: skill.name in user.disabled_skills
    effect: deny
    priority: 200

# 默认策略
default:
  effect: deny
```

## 2. 策略转换引擎

```python
# core/policy/markdown_to_rego.py
class MarkdownPolicyConverter:
    """Markdown 策略转 Rego 转换器"""
    
    def convert(self, markdown_content: str) -> str:
        """Markdown → Rego"""
        policy = self._parse_markdown(markdown_content)
        
        rego_parts = [
            f'package {policy.name.replace("-", ".")}',
            '',
            'default allow := false',
            '',
        ]
        
        # 生成规则
        for rule in sorted(policy.rules, key=lambda r: r.priority):
            rego_parts.extend(self._rule_to_rego(rule))
        
        return '\n'.join(rego_parts)
    
    def _rule_to_rego(self, rule: PolicyRule) -> List[str]:
        """单个规则转 Rego"""
        lines = [
            f'# {rule.id}',
            f'allow if {{',
        ]
        
        # 条件
        if rule.conditions:
            for cond in rule.conditions:
                lines.append(f'    {self._expr_to_rego(cond)}')
        else:
            lines.append(f'    {self._expr_to_rego(rule.condition)}')
        
        lines.append('}')
        
        # 效果条件
        if rule.effect_conditions:
            lines.append(f'allow if {{')
            for ec in rule.effect_conditions:
                lines.append(f'    not ({self._expr_to_rego(ec)})')
            lines.append('}')
        
        return lines
```

## 3. 策略热更新机制

```python
# core/policy/hot_reload_manager.py
class PolicyHotReloadManager:
    """策略热更新管理器"""
    
    def __init__(self, opa_client: OPAClient):
        self.opa = opa_client
        self.version_manager = PolicyVersionManager()
        self.bundle_server = BundleServer()
    
    async def reload_policy(self, policy_name: str, markdown_content: str):
        """
        热更新单个策略
        流程: Markdown → Rego → Version → Bundle → OPA
        """
        # 1. Markdown → Rego
        converter = MarkdownPolicyConverter()
        rego_content = converter.convert(markdown_content)
        
        # 2. 版本管理
        version = await self.version_manager.create_version(
            policy_name=policy_name,
            content=rego_content,
            checksum=self._md5(rego_content)
        )
        
        # 3. 生成 Bundle
        bundle = await self.bundle_server.create_bundle([
            PolicyBundle(
                name=policy_name,
                files=[{
                    "path": f"policies/{policy_name}.rego",
                    "content": rego_content
                }]
            )
        ])
        
        # 4. 推送到 OPA
        await self.opa.load_bundle(bundle)
        
        # 5. 发布更新事件
        await self.event_bus.publish(PolicyReloadedEvent(
            policy_name=policy_name,
            version=version,
            timestamp=datetime.now()
        ))
    
    async def batch_reload(self, policies: List[Policy]):
        """批量热更新"""
        async with self._lock:
            for policy in policies:
                await self.reload_policy(policy.name, policy.markdown_content)
    
    async def rollback(self, policy_name: str, target_version: str):
        """回滚到指定版本"""
        version = await self.version_manager.get_version(policy_name, target_version)
        await self.reload_policy(policy_name, version.content)
```

## 4. 策略管理界面设计

```typescript
// frontend: PolicyManagement
const PolicyManagement: React.FC = () => {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);
  const [testInput, setTestInput] = useState<TestInput>({});
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  // 策略列表
  const policyList = policies.map(p => ({
    key: p.name,
    label: p.name,
    version: p.version,
    status: p.enabled ? 'active' : 'inactive'
  }));

  // Markdown 编辑器
  const handleMarkdownChange = async (markdown: string) => {
    setSelectedPolicy({ ...selectedPolicy, markdown_content: markdown });
  };

  // 实时预览 Rego
  const handlePreview = async () => {
    const rego = await api.convertMarkdownToRego(selectedPolicy.markdown_content);
    setSelectedPolicy({ ...selectedPolicy, rego_content: rego });
  };

  // 在线测试
  const handleTest = async () => {
    const result = await api.testPolicy({
      policy_name: selectedPolicy.name,
      input: testInput
    });
    setTestResult(result);
  };

  // 保存并生效
  const handleSaveAndApply = async () => {
    await api.saveAndReload(selectedPolicy);
    message.success('策略已更新并生效');
  };

  // 版本历史
  const handleViewHistory = async () => {
    const versions = await api.getPolicyVersions(selectedPolicy.name);
    setSelectedPolicy({ ...selectedPolicy, versions });
  };

  // 回滚
  const handleRollback = async (version: string) => {
    await api.rollbackPolicy(selectedPolicy.name, version);
    message.success('已回滚到指定版本');
  };

  return (
    <Split horizontal defaultSizes={[250, '1fr']}>
      {/* 左侧：策略列表 */}
      <Panel header="策略列表">
        <Tree
          treeData={policyList}
          onSelect={(keys) => {
            const policy = policies.find(p => p.name === keys[0]);
            setSelectedPolicy(policy);
          }}
        />
        <Button onClick={handleCreateNew}>新建策略</Button>
      </Panel>

      {/* 右侧：策略编辑器 */}
      <Panel header={selectedPolicy?.name}>
        <Tabs>
          <TabPane key="editor" tab="编辑器">
            <Row gutter={16}>
              <Col span={12}>
                <Title level={5}>Markdown 格式</Title>
                <MarkdownEditor
                  value={selectedPolicy?.markdown_content}
                  onChange={handleMarkdownChange}
                  height={400}
                />
                <Button onClick={handlePreview}>预览 Rego</Button>
              </Col>
              <Col span={12}>
                <Title level={5}>Rego 输出</Title>
                <CodeBlock
                  code={selectedPolicy?.rego_content || ''}
                  language="rego"
                  height={400}
                />
              </Col>
            </Row>
          </TabPane>

          <TabPane key="test" tab="在线测试">
            <Form layout="vertical">
              <Form.Item label="测试输入 (JSON)">
                <TextArea
                  value={JSON.stringify(testInput, null, 2)}
                  onChange={(e) => setTestInput(JSON.parse(e.target.value))}
                  rows={10}
                />
              </Form.Item>
              <Button onClick={handleTest}>执行测试</Button>
            </Form>
            
            {testResult && (
              <Result
                allowed={testResult.allowed}
                reasons={testResult.reasons}
                trace={testResult.trace}
              />
            )}
          </TabPane>

          <TabPane key="history" tab="版本历史">
            <Timeline>
              {selectedPolicy?.versions.map(v => (
                <Timeline.Item key={v.version}>
                  <Text strong>{v.version}</Text>
                  <Text type="secondary">{v.created_at}</Text>
                  <Text>{v.changes}</Text>
                  <Button onClick={() => handleRollback(v.version)}>回滚</Button>
                </Timeline.Item>
              ))}
            </Timeline>
          </TabPane>
        </Tabs>

        <Button type="primary" onClick={handleSaveAndApply}>
          保存并生效
        </Button>
      </Panel>
    </Split>
  );
};
```

## 5. MVP 快速验证策略

| MVP 阶段 | 策略 | 说明 |
|----------|------|------|
| **Phase 0** | 简化 OPA | 单 Bundle + 手动推送 |
| **Phase 1** | Markdown 策略 | 策略转换 + 在线测试 |
| **Phase 2** | 热更新 | Bundle 自动推送 |
| **Phase 3** | 完整管理 | 版本管理 + 回滚 + 审计 |

```python
# core/policy/mvp_policy_manager.py
"""
MVP 快速验证 - 简化策略管理器
"""
class MVPClaimManager:
    """MVP 阶段使用，简单直接"""
    
    def __init__(self, opa_url: str = "http://localhost:8181"):
        self.opa = OPAClient(url=opa_url)
        self.policies_dir = Path("policies/mvp")
    
    async def check(self, user: str, action: str, resource: str) -> bool:
        """极简权限检查"""
        return await self.opa.evaluate({
            "input": {"user": user, "action": action, "resource": resource}
        })
    
    async def reload_all(self):
        """手动重载所有策略"""
        for policy_file in self.policies_dir.glob("*.rego"):
            content = policy_file.read_text()
            await self.opa.put_policy(policy_file.stem, content)
    
    async def create_policy(self, name: str, markdown: str):
        """创建策略 (Markdown → Rego → OPA)"""
        converter = MarkdownPolicyConverter()
        rego = converter.convert(markdown)
        
        policy_file = self.policies_dir / f"{name}.rego"
        policy_file.write_text(rego)
        
        await self.opa.put_policy(name, rego)
```

## 6. 全场景策略覆盖

| 场景 | 包路径 | 说明 |
|------|--------|------|
| **身份权限** | `auth.rbac` | 用户角色、资源访问 |
| **Skill 权限** | `skill.permission` | 技能执行、参数校验 |
| **本体访问** | `ontology.access` | 节点读写、属性过滤 |
| **数据权限** | `data.workspace` | 工作空间数据隔离 |
| **API 网关** | `api.gateway` | 请求速率、IP 白名单 |
| **UI 权限** | `ui.config` | 界面元素、菜单项 |

**后果**:
- ✅ **全场景覆盖**：OPA 一个引擎覆盖所有策略场景
- ✅ **Markdown 友好**：降低 Rego 学习成本
- ✅ **可视化**：管理界面支持图形化编辑和测试
- ✅ **热更新**：策略修改即时生效，无需重启
- ✅ **版本控制**：完整策略历史，支持回滚
- ✅ **Fail-close**：默认拒绝，安全性高
- ❌ 引入 OPA 服务（Docker 容器）
- ❌ Markdown → Rego 转换需维护

**可逆性**: 中。保留 JSON 格式可降级到纯 Rego。

---