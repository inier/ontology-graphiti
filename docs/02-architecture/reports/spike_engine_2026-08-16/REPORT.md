# ADR-075 Phase 2 引擎 Spike 验收报告

- **日期**：2026-08-16
- **范围**：确定性推理引擎选型对决 **pyDatalog vs experta**（ADR-075 grilling 决议项）
- **验收标准**（ADR-075 2026-08-16 决议）：规则集 100 条 + 事实 10k 条，单次推理 **P95 < 500ms**，rule_trace 完整输出（含 `matched_facts`/`derived_fact`）
- **环境**：Python 3.13.13 · pyDatalog 0.17.4 · experta 0.9.2（Windows 11，本机 uv 沙箱，未污染项目依赖）
- **复现**：`uv run --no-project --python 3.13 --with pyDatalog python spike_pydatalog.py [A|B|C]`

---

## 1. 结论速览

| 判定项 | 结果 | 说明 |
|---|---|---|
| **experta 兼容性** | ❌ **出局** | 0.9.2 硬锁 `frozendict==1.2`（依赖 `collections.Mapping`，Python 3.10+ 已移除），不可升级，**3.10+ 全线不可用** |
| **pyDatalog 安装/导入** | ✅ 通过 | 0.17.4 在 3.13 可安装可运行（仅 1 处 `SyntaxWarning: invalid escape sequence`，无功能影响） |
| **非递归规则性能** | ✅ 通过 | 场景 A 1.9ms / 场景 B 255ms（P95），均 < 500ms |
| **递归规则性能** | ❌ 不通过 | 全量递归传递闭包在 500 节点/800 边即超时（>120s）；受限起点查询才 0.7ms（样本失真） |
| **全量演绎性能** | ❌ 不通过 | 全量 90 谓词演绎 P95 = 16.1s（非验收场景，但必须规避） |
| **rule_trace 完整性** | ✅ 通过 | step 化 trace（`step`/`rule_id`/`rule_text`/`matched_facts`/`derived_fact`）构建 < 1ms，与 ADR-076 `reasoning_trace` 字段对齐 |

## 2. 性能数据

事实集 12,000（node 5k + rel 5k + attr 2k），规则 100 条，每场景 20 次采样：

| 场景 | 查询 | 结论数 | P50 | P95 | 判定 |
|---|---|---|---|---|---|
| A 轻量类型推断链 | `combo_c3(N)` | 1 | 1.5ms | **1.9ms** | ✅ |
| B 3-hop 关系组合 | `derived_d0(X, Z)` | 54 | 228.4ms | **255.4ms** | ✅ |
| C 递归传递闭包（受限起点） | `ancestor('r1', Y)` | 1 | 0.4ms | **0.7ms** | ⚠️ 样本失真 |
| — 递归闭包（无约束全量） | `ancestor(X, Y)` | 超时 | — | — | ❌ |
| — 全量 90 谓词演绎 | 全部派生谓词 | 147,518 | 15.5s | **16.1s** | ❌ |

## 3. 关键发现

1. **experta 无法进入 3.10+ 部署环境**：其唯一依赖 `frozendict==1.2` 使用已删除的 `collections.Mapping`，且版本被钉死（`uv` 解析冲突证明不可覆盖）。**确定性引擎唯一候选 = pyDatalog**。
2. **pyDatalog 的演绎是"目标驱动 + 全量物化"混合**：单个目标查询快（<300ms），但无约束查询/递归会触发全量求值导致组合爆炸。
3. **结论物化规模是性能瓶颈**：全量演绎物化 147k 结论 → 16s；业务推理必须**目标化**（指定谓词 + 绑定常量），禁止无约束全量求值。
4. **rule_trace 可低开销实现**：trace 构建与推理解耦，<1ms 开销满足审计要求。

## 4. 架构含义（影响 ADR-075 定案）

| 议题 | 建议 |
|---|---|
| 引擎选型 | **定案 pyDatalog**（experta 出局）；回退项改为 ADR-075 §Considered Options 5「自研前向链接器」（仅当 pyDatalog 递归硬伤无法在业务侧规避时启用） |
| 推理入口约束 | `ReasoningServiceContract` 的推理 API 一律**目标化查询**（`query(goal, bindings)`），禁止无约束全量演绎；由服务层强制（spike 数据作为契约测试基准） |
| 递归规则治理 | 递归规则集**上限**（建议 ≤ 5 条/本体版本）且仅允许"受限起点"调用；超限或全量递归请求返回 `RuleExecutionError(RECURSION_LIMIT)`，降级为：①Neo4j Cypher 可变长度路径（`[r*1..k]`）或 ②迭代展开（自研 200 行 forward chaining 兜底，ADR-075 §Considered Options 5） |
| 结论规模上限 | 单次推理结论数上限（建议 10k），超出返回截断 + `truncated: true` 标记（ADR-076 `reasoning_trace` 兼容） |
| 超时预算 | 单规则执行超时 500ms（ADR-075 hybrid 裁决），由服务层 `futures` 包裹执行 |
| 依赖引入 | `pyDatalog==0.17.4` 加入 `apps/api/pyproject.toml`；需 `bootstep.py rebuild main`（ADR-075 Consequences 已列明） |

## 5. 后续工作项

1. ADR-075 依本报告定案：写入「引擎选型 = pyDatalog」+ §4 架构约束
2. `apps/api/odap/biz/core/ontology/reasoning/` 落地：`fact_loader` / `rule_loader`（含 §3.1 白名单校验）/ `engine.py`（pyDatalog 封装）/ `trace_builder` / `temporal_algebra.py`（Allen 13 关系）
3. `ReasoningServiceContract` 适配器实现（ADR-072 §5 能力表）
4. `state_at()` 落位 `infra/graph`（GraphManager 增强）
5. 对拍测试：`health/` 5 类校验新旧结果比对（ADR-075 §5.1）
