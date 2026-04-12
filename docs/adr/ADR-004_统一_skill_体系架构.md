# ADR-004: 统一 Skill 体系架构

> **来源**: `docs/ARCHITECTURE.md` 第 17 章

---


**状态**: 已接受

**上下文**: 现有 Python Skills 积累需要与 OpenHarness Markdown Skills 生态统一，实现技能的热插拔和统一管理。

**决策**: 统一到 OpenHarness Skill 体系，采用 Markdown 定义 + Python 实现的双层结构：

```
┌─────────────────────────────────────────────────────────────────┐
│                      OpenHarness Skill 生态                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐  │
│  │   Markdown    │    │   Python      │    │   Skill       │  │
│  │   Definition  │ →  │   Executor    │ →  │   Registry    │  │
│  │   (SKILL.md)  │    │   (Wrapper)   │    │   (Hot Reload)│  │
│  └───────────────┘    └───────────────┘    └───────────────┘  │
│         ↑                    ↑                    ↑            │
│         │                    │                    │            │
│  ┌──────┴────────────────────┴────────────────────┴──────┐    │
│  │                    Skill 元数据                         │    │
│  │  name, version, category, inputs, outputs, permissions  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

**Skill 结构规范**：

```yaml
# SKILL.md - Skill 元数据定义
name: "battlefield_situation"
version: "1.0.0"
category: "intelligence"  # intelligence | operations | analysis | visualization
description:
  zh: "战场态势分析技能"
  en: "Battlefield Situation Analysis Skill"
permissions:  # OPA 策略关联
  - "read:ontology"
  - "read:simulation_data"
inputs:
  - name: "query"
    type: "string"
    required: true
  - name: "workspace_id"
    type: "string"
    required: true
outputs:
  - name: "situation_report"
    type: "object"
python_executor: "skills/intelligence/battlefield_situation.py"  # Python 实现路径
hot_reload: true  # 支持热更新
```

**统一 Skill 注册流程**：

```python
# core/skill_registry.py
class SkillRegistry:
    """统一 Skill 注册中心"""
    
    def register(self, skill_path: str) -> SkillMetadata:
        """注册 Skill"""
        # 1. 解析 SKILL.md
        metadata = self._parse_skill_md(skill_path)
        
        # 2. 验证 Python Executor 存在
        executor_path = skill_path / metadata.python_executor
        if not executor_path.exists():
            raise SkillValidationError(f"Executor not found: {executor_path}")
        
        # 3. 加载到内存
        module = importlib.import_module(
            metadata.python_executor.replace("/", ".").replace(".py", "")
        )
        metadata.executor = getattr(module, "execute")
        
        # 4. 注册到 OPA
        self._register_permissions(metadata)
        
        # 5. 发布事件
        event_bus.publish(SkillRegisteredEvent(metadata))
        
        return metadata
    
    def unregister(self, skill_name: str) -> bool:
        """注销 Skill"""
        # 1. 从内存移除
        metadata = self._skills.pop(skill_name)
        
        # 2. 从 OPA 移除权限
        self._unregister_permissions(metadata)
        
        # 3. 发布事件
        event_bus.publish(SkillUnregisteredEvent(skill_name))
        
        return True
```

**后果**:
- ✅ 统一管理：所有 Skill 通过 Registry 集中管理
- ✅ 热插拔：新增/禁用/启用无需重启
- ✅ 权限控制：Skill 级别权限与 OPA 策略绑定
- ✅ 标准化：与 OpenHarness 生态完全兼容
- ✅ 可追溯：Skill 版本历史、依赖关系清晰
- ❌ 迁移成本：现有 Python Skills 需要包装成统一格式
- ❌ 学习成本：需要遵循 Skill 定义规范

**可逆性**: 中。保留 Python 模块可降级到纯 Python 调用。

---