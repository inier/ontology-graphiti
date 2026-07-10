# ADR-061: 领域 Skill 插件化打包与契约测试

## 状态
Accepted

## 上下文

ODAP 的 Skill 体系已具备热插拔（ADR-014）与统一工具注册表（ADR-029），当前所有领域 Skill 位于单体目录 `odap/tools/`（intelligence / operations / analysis / planning ...）。随着领域 Skill 数量增长（目标 56+ 领域）与多团队并行贡献，出现三类问题：

1. **部署耦合**：任一 Skill 的导入/初始化错误会导致整个 FastAPI 进程启动失败。
2. **无法独立版本化**：Skill 与平台同仓同发版，无法对单个领域 Skill 做灰度/回滚。
3. **边界靠人工**：ADR-046 已明确标注"模块间耦合逐渐松弛"为**高风险**，仅靠代码审查约束 `ISkill` 边界不可持续。

约束（沿用 ADR-046）：维持模块化单体、单进程、无微服务、团队 3–5 人。

## 决策

采用 **Skill 插件包（Plugin Package）** 模式，而非 Skill 微服务或沙箱：

1. **契约接口 `ISkill`**：在现有 `BaseSkill`（`odap/tools/base.py`）之上固化契约——`execute / validate / metadata / resource_bounds`，所有 Skill 必须实现。
2. **领域插件包**：以"领域"为单位的独立包（Python wheel 或带 `skill.yaml` 清单的目录），含版本号与依赖声明；通过 entry-point / 清单发现，中央 `SkillRegistry`（ADR-029）聚合。
3. **复用热插拔**：加载/卸载沿用 ADR-014 机制，支持运行时热加载且不重启进程。
4. **契约测试（CI 门禁）**：每个插件在 CI 中跑契约测试，验证实现 `ISkill`、资源边界（超时/内存）、注册元数据合法。**架构依赖方向测试**（ArchUnit 风格）禁止 `tools/` 反向依赖 `biz/`/`web/`。
5. **灰度与回滚**：插件版本独立，支持按 `workspace_id` 启用不同版本（复用 ADR-041 隔离维度）。

### 结构示意

```
skills/
├── intelligence-radar/        # 独立包
│   ├── skill.yaml             # name, version, depends, resource_bounds
│   └── plugin.py              # class RadarSkill(ISkill)
├── operations-strike/
│   └── ...
└── registry-manifest.json     # 启用清单（按需裁剪）
```

## 后果

### 变得更容易
- 多团队并行：各团队独立打包/发版自己的领域 Skill，不再互相阻塞。
- 故障隔离：单个插件加载失败仅影响该插件（热插拔隔离），不拖垮进程。
- 边界可验证：CI 强制契约 + 依赖方向测试，替代人工审查。
- 灰度可控：插件版本与 workspace 绑定，可按场景灰度。

### 变得更难
- 打包/发布流水线复杂度上升（一次性投入，需构建与索引插件）。
- 插件间依赖解析（版本冲突）需治理策略。
- 调试跨插件调用链路需可观测性支撑（见 ADR-064）。

## 可逆性
**高**。插件包可回退为目录式 Skill（移除发现/打包层即可）；接口契约不变，下游注册表与调用方无感。

## 关联
- ADR-014（Skill 热插拔，复用加载机制）
- ADR-029（工具注册表，聚合入口）
- ADR-046（模块化单体，维持单进程基线）
- ADR-064（可观测性，支撑跨插件追踪）
