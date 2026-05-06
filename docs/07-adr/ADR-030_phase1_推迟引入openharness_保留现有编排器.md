# ADR-030: Phase 1 推迟引入 OpenHarness，保留现有编排器

## 状态
已接受 | **创建日期**: 2026-04-13 | **优先级**: P1

## 上下文

### 问题陈述

ADR-025 已确定 Phase 2 采用 OpenHarness 作为多 Agent 协同的内核。进入 Phase 1-A 基础设施验证阶段时，需要决定：**是否立即将 OpenHarness 引入现有代码库**，还是推迟到 Phase 2。

### 触发因素

1. **Phase 1 目标**：Intelligence Agent 单体闭环（分析 B 区威胁 → 输出结构化报告）
2. **现有能力**：`SelfCorrectingOrchestrator` 基于关键词正则路由，已满足单 Agent 场景
3. **OpenHarness 引入代价**：
   - 安装：`pip install openharness`（约 11K LOC 框架依赖）
   - 需要理解 Tool / Skill / Provider / Coordinator 接口，适配工作量约 2-3 周
   - 引入后需要同时维护两套注册机制，增加复杂度
4. **风险评估**：OpenHarness 是相对活跃的开源项目，API 可能在 Phase 1 期间变化

### 已考虑的选项

| 方案 | 描述 | 风险 |
|------|------|------|
| **A. 立即引入（完全替换）** | 用 OpenHarness engine 替换 `SelfCorrectingOrchestrator` | 工作量 2-3 周，可能阻塞 Phase 1-B Demo | 高 |
| **B. 立即引入（并行试验）** | 新建 `core/openharness_agent.py`，现有路径保持不变 | 两套并存，但不阻塞 Phase 1 | 中 |
| **C. 推迟到 Phase 2（本决策）** | Phase 1 保留现有编排器，完成 OpenHarness 接口调研文档 | Phase 2 引入时可能需要额外重构 | 低 |

---

## 决策

**采用方案 C：Phase 1 推迟引入 OpenHarness。**

具体行动：
1. Phase 1-A：完成 OpenHarness 接口调研（安装 → 理解 Tool 格式 → 写接口文档），不写入生产代码
2. Phase 1-B：Intelligence Agent 使用现有 `SelfCorrectingOrchestrator` + `BaseSkill`
3. Phase 2 开始时：基于 ADR-025 的渐进式策略正式引入

**触发重新评估的条件**（满足任一条即可提前引入）：
- Phase 1-A 结束时 OpenHarness 的 Skill 接口已稳定，适配工作 < 1 周
- 现有编排器出现设计局限，无法支撑 Phase 1-B 的 Demo 需求
- 团队增加了有 OpenHarness 经验的成员

---

## 后果

### 变得更容易
- Phase 1 进度不被框架适配阻塞
- `BaseSkill` 的 API 设计可以更自由，不必提前对齐 OpenHarness Tool 接口
- 如果 OpenHarness API 在 Phase 1 期间变化，不影响已有代码

### 变得更难
- Phase 2 引入 OpenHarness 时，现有 Skill 注册机制（`SkillRegistry` + `SKILL_CATALOG`）需要双向桥接
- 如果 Phase 2 拖期，OpenHarness 的集成价值会延迟体现

### 架构影响
- `skills/base.py` 的 `BaseSkill` 接口设计应保持与 OpenHarness Tool 接口**概念对齐**（均有 name/description/execute），便于 Phase 2 桥接
- `SelfCorrectingOrchestrator` 不做大规模重构，仅做必要的 Bug 修复和 Phase 1-B 功能扩展

---

## 可逆性

**高**。

Phase 1 的所有代码（`BaseSkill`、`SkillRegistry`、现有编排器）可以在 Phase 2 保留并逐步迁移，无需重写。最坏情况是 Phase 2 引入 OpenHarness 时需要重构编排层，但 Skill 层可以通过适配器保持兼容。

---

## 附录：OpenHarness 接口概要（调研结果）

以下是 Phase 1-A 调研结论，供 Phase 2 桥接参考：

### Tool / Skill 格式对比

| 维度 | OpenHarness Tool | 本项目 BaseSkill |
|------|-----------------|----------------|
| 定义方式 | `@tool` 装饰器 或继承 `BaseTool` | 继承 `BaseSkill` |
| 输入模型 | Pydantic `BaseModel` + schema | `SkillInput(BaseModel)` |
| 输出格式 | 返回字符串或结构化 dict | `SkillOutput(BaseModel)` |
| 元数据 | `name` / `description` 属性 | `SkillMetadata` 对象 |
| 权限检查 | Middleware / Permissions 插件 | `requires_opa_check` 标记 |

**兼容性评估**: `BaseSkill.execute()` → OpenHarness Tool 的适配器层约 50-100 行代码。

### 建议的桥接点（Phase 2 实施）

```python
# Phase 2 桥接示意（不在 Phase 1 实现）
class OpenHarnessToolAdapter:
    """将 BaseSkill 包装为 OpenHarness Tool"""

    def __init__(self, skill: BaseSkill):
        self.skill = skill
        self.name = skill.metadata.name
        self.description = skill.metadata.description

    def __call__(self, **kwargs):
        result = self.skill.run(kwargs)
        if not result.success:
            raise RuntimeError(result.error)
        return result.data
```

### 安装验证

```bash
# 验证 OpenHarness 是否可安装（在独立虚拟环境中测试）
pip install openharness
oh --version  # 期望输出版本号
```

> 注意：Phase 1-A 阶段在独立虚拟环境验证，不加入 requirements.txt。
> 加入 requirements.txt 是 Phase 2 引入时的操作（新增 ADR）。

---

*本 ADR 在 TASK_BREAKDOWN.md § 7 D1 决策点基础上细化记录。*
