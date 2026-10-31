---
id: odap.l15.plans-2026-09-27-persist-records-dry-refactor
status: reference
owner: architect
version: ''
layer: L15
concern: design-spec-record
lifecycle: historical
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: superpowers 实施计划存档，计划已执行，保留为执行留痕
governance_evidence: docs/superpowers/specs/ 存在同名 design 文档（spec/plan 成对）
---

# `_persist_records` DRY 重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `pipeline_service.py` 中 3 处逐字重复的「候选批量落库 + 失败显式报错」代码块抽成单一私有方法 `_persist_records`，消除重复且零行为变更。

**Architecture:** 这是一个 extract-method（提炼方法）重构。当前 `_collect_structured_candidates`、`_collect_event_candidates`、`_collect_indicator_candidates` 三个归集器各自内联一段 `if records: try: bulk_insert_candidates(...) except: logger.error(...) + return {"status":"error"}` 代码块，三块除标签词（"结构化"/"事件"/"BI 指标"）外逐字相同。抽出一个 `_persist_records(records, label) -> Optional[Dict]` 私有方法承载这段逻辑，三个归集器改为调用它。落库成功或空记录返回 `None`，失败返回显式 error dict —— 与现状完全一致（AGENTS.md 规则 2 + 规则 14：落库失败绝不能当成假成功）。

**Tech Stack:** Python 3.10+ · FastAPI · Pydantic v2 · SQLite（候选存储）· pytest（离线单测）· import-linter（C1-C4 架构契约）。

**Spec:** 本计划源自 ADR-082 分支终审（final whole-branch review）登记的 **parked finding (a)**：`_add`+落库三处重复。brainstorming 走 **Bounded** 路径（无独立 spec 文件），设计已在对话中获用户批准（"批准，生成详细实现计划"）。范围经用户明确收敛为 **只做 (a)** —— finding (b) `event_id` 重命名、finding (c) 函数长度守卫修复均 **不在本计划范围**。上游背景见：
- `docs/superpowers/plans/2026-09-25-event-source-bi-indicator-ol-entries.md`（ADR-082 实现计划，本重构所改的 3 个归集器由该计划的 Task 2/4 引入）
- `.superpowers/sdd/2026-09-25-event-source-bi-indicator-ol-entries/progress.md`（SDD 台账，含 finding (a) 的完整裁定记录；git-ignored）

## Global Constraints

以下约束对每个 Task 隐式生效，逐字来自 AGENTS.md 与用户既定决策：

- **执行时机硬门禁**：本重构 **必须等用户先提交 ADR-082 的 7 个文件之后** 才开始执行。目的是让 ADR-082 的交接保持干净，并使本重构成为一个 **可独立 revert 的单独提交**（AGENTS.md §F：原子逻辑变更单元）。执行者开工前先 `git rev-parse HEAD` 记录 BASE —— 该 BASE 应为用户提交 ADR-082 后的新 commit，而非 `2bef7b0`。若发现 ADR-082 的 7 个文件仍未提交（`git status` 里仍是 modified/untracked），**停止并告知用户先提交**，不得抢先执行。
- **提交策略「最后你来」**：执行者 **不自行 `git commit`/merge/push**。每个 Task 完成并通过验证后，执行者按文件名精确 `git add`（**禁止 `git add -A`** —— 工作区有约 92 个无关未提交文件），然后把建议的原子提交边界与 message 交给用户，由用户统一提交。下方每个 Task 的 commit 步骤给出的是 **建议边界与 message 文案**，供用户执行，不代表执行者会自动提交。
- **只改 2 个文件**：`apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py`（加 helper + 改 3 处调用）与 `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py`（加 3 个直测）。不得触碰其它文件，尤其不得顺手改 finding (b)/(c)。
- **零行为变更**：重构后 3 个归集器的日志字符串、error message 字符串、返回结构、`if records` 空记录语义必须与重构前 **逐字一致**。标签词（"结构化"/"事件"/"BI 指标"）通过 `label` 参数原样传入。行为保持的证据 = 既有 61 条测试 **不改一行** 全绿。
- **规则 14（禁止未经确认和评审的兜底逻辑）**：helper 内 `except` **不得** 静默吞异常或降级为成功 —— 必须 `logger.error` + 返回显式 error dict（与现状一致）。第 6 条「测试必须执行真实函数体」：新增直测 **只在存储边界 patch `candidate_storage.bulk_insert_candidates`**，绝不 patch 被测方法 `_persist_records` 本身，确保 helper 真实函数体被执行。
- **离线 pytest 调用式（不遵守会永久挂起）**：所有 pytest 命令从 **仓库根** 以如下形式运行：
  `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest <target> -q --no-header -p no:cacheprovider`
- **lint-imports 调用式**：`cd apps/api && uv run --frozen --no-sync lint-imports`（C1-C4 契约定义在 `apps/api/pyproject.toml`；本重构是 biz 内部私有方法提炼，不新增任何跨层/跨域 import，契约应保持全绿）。
- **规则 7（Podman）**：本重构是纯 Python 后端逻辑，验证只跑离线单测 + lint-imports，**不需要** 起容器；禁止在宿主机直接 `uvicorn`。
- **规则 12（文档同步）**：本重构是私有方法提炼，**不触发** 任何文档同步条件（无新增/删除模块、无路由/API/env/schema 变更、无架构级决策）。ADR-082 已在 `docs/03-modules/semantic_admin/DESIGN.md §4.5` 记录的行为不因本重构改变，故 **无需改文档**。Task 2 含一步显式确认「无文档同步触发」以免执行者漏检。

---

## File Structure

| 文件 | 职责 | 本重构的改动 |
|------|------|------------|
| `apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py` | 语义资产归集管线（`SemanticAssetPipeline` 类，含 3 个 `_collect_*_candidates` 归集器） | 新增私有方法 `_persist_records`（置于 `_collect_structured_candidates` 之前，当前第 862 行处）；3 个归集器各自的内联落库块替换为 3 行调用 |
| `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py` | 该管线的单测（当前 61 条，覆盖结构化/事件/指标三源归集、落库、审批提交、失败显式化等） | 新增 1 个测试类 `TestPersistRecordsHelper`（3 条直测：空→None / 成功→None / 失败→显式 error dict）；既有 61 条 **一行不改** |

### 重构前后结构对照

**重构前**（3 处逐字重复，仅标签词不同）—— 以结构化为例（`pipeline_service.py:1038-1048`）：

```python
        if records:
            # 落库失败绝不能当成成功：返回未持久化的候选会让调用方报出
            # candidate_count>0，而 get_run 再查时一条都没有（规则 14：假成功）。
            try:
                self.candidate_storage.bulk_insert_candidates(records)
            except Exception as e:
                logger.error("结构化候选归集落库失败: %s", e)
                return {
                    "status": "error",
                    "message": f"结构化候选落库失败（{len(records)} 条未持久化）: {e}",
                }
```

（事件块在 `1235-1243`，标签 "事件"；BI 指标块在 `1334-1342`，标签 "BI 指标"；两块 **无** 结构化块那两行解释性注释。）

**重构后** —— helper 承载逻辑，3 处各缩为 3 行调用：

```python
        persist_err = self._persist_records(records, "结构化")   # 事件处传 "事件"；指标处传 "BI 指标"
        if persist_err:
            return persist_err
```

净效果：每处缩短约 8 行，重复消除，行为逐字保持。

---

## Task 1: 新增 `_persist_records` helper + 直测（TDD）

**Files:**
- Modify: `apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py`（在第 862 行 `def _collect_structured_candidates(` 之前插入新方法）
- Test: `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py`（追加新测试类 `TestPersistRecordsHelper`）

**Interfaces:**
- Consumes: `self.candidate_storage.bulk_insert_candidates(records: List[Dict[str, Any]])`（既有存储边界方法，成功无返回/失败抛异常）；模块级 `logger`（`pipeline_service.py:25`）；`typing` 的 `Any, Dict, List, Optional`（`pipeline_service.py:17` 已导入）。
- Produces（供 Task 2 的 3 处调用消费，签名逐字固定）:
  ```python
  def _persist_records(
      self, records: List[Dict[str, Any]], label: str
  ) -> Optional[Dict[str, Any]]:
  ```
  契约：`records` 为空 → 返回 `None`（不触碰存储）；落库成功 → 返回 `None`；落库抛异常 → `logger.error("%s候选归集落库失败: %s", label, e)` 并返回 `{"status": "error", "message": f"{label}候选落库失败（{len(records)} 条未持久化）: {e}"}`。

- [ ] **Step 1: 记录 BASE**

Run: `git rev-parse HEAD`
Expected: 打印一个 commit hash（应为用户提交 ADR-082 后的新 commit，**不是** `2bef7b0`）。把它记为本计划的 BASE，供 review-package 与后续 diff 使用。

- [ ] **Step 2: 确认 ADR-082 已提交（执行时机硬门禁）**

Run: `git status --short apps/api/odap/biz/data/ingest/unified_ingest_facade.py apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py docs/03-modules/semantic_admin/DESIGN.md`
Expected: **无输出**（这三个 ADR-082 文件已 clean，说明用户已提交）。
若仍有 `M`/`??` 输出 → **停止**，告知用户「ADR-082 尚未提交，本重构须在其之后执行」，不要继续。

- [ ] **Step 3: 写失败测试（3 条直测）**

在 `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py` **文件末尾** 追加以下测试类（逐字，`pipeline` fixture 见该文件第 70-85 行，注入真 `SQLiteCandidateStorage`）：

```python
class TestPersistRecordsHelper:
    """_persist_records 直测：空→None / 成功→None / 失败→显式 error dict。

    走真实函数体（规则 14 第 6 条）—— 仅在存储边界 patch
    bulk_insert_candidates，绝不 patch 被测方法 _persist_records 本身。
    """

    def test_empty_records_returns_none_without_touching_storage(
        self, pipeline, monkeypatch,
    ):
        def _boom(_records):
            raise AssertionError("空记录不应触发落库")

        monkeypatch.setattr(
            pipeline.candidate_storage, "bulk_insert_candidates", _boom, raising=True,
        )
        assert pipeline._persist_records([], "结构化") is None

    def test_success_returns_none_and_writes_records(self, pipeline, monkeypatch):
        seen = {}

        def _capture(records):
            seen["records"] = records

        monkeypatch.setattr(
            pipeline.candidate_storage, "bulk_insert_candidates", _capture, raising=True,
        )
        records = [{"canonical": "c1"}, {"canonical": "c2"}]
        assert pipeline._persist_records(records, "事件") is None
        assert seen["records"] is records

    def test_failure_returns_explicit_error_with_label_and_count(
        self, pipeline, monkeypatch,
    ):
        def _boom(_records):
            raise RuntimeError("disk full")

        monkeypatch.setattr(
            pipeline.candidate_storage, "bulk_insert_candidates", _boom, raising=True,
        )
        records = [{"canonical": "c1"}, {"canonical": "c2"}, {"canonical": "c3"}]
        out = pipeline._persist_records(records, "BI 指标")
        assert out is not None
        assert out["status"] == "error", out
        assert "disk full" in out["message"]
        assert "BI 指标" in out["message"]
        assert "3 条未持久化" in out["message"]
```

- [ ] **Step 4: 运行测试，确认 RED（方法尚未存在）**

Run（仓库根）:
```bash
PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py::TestPersistRecordsHelper -q --no-header -p no:cacheprovider
```
Expected: **FAIL**，3 条全部报 `AttributeError: 'SemanticAssetPipeline' object has no attribute '_persist_records'`（或等价的属性缺失错误）。这是正确的 RED —— 证明测试真的在验证 helper 存在。

- [ ] **Step 5: 实现 `_persist_records`（最小实现）**

在 `pipeline_service.py` 中，`_collect_structured_candidates` 定义（当前第 862 行 `    def _collect_structured_candidates(`）**之前** 插入以下方法（逐字，缩进为类内方法 4 空格）。Edit 锚点：`_load_ontology_documents` 的结尾 `return {"documents": documents, "unreadable_doc_ids": unreadable, "error": None}`（第 860 行）+ 空行 + `def _collect_structured_candidates(`：

```python
    def _persist_records(
        self, records: List[Dict[str, Any]], label: str
    ) -> Optional[Dict[str, Any]]:
        """候选批量落库。成功或空记录 → None；失败 → 显式 error dict。

        规则 14：落库失败绝不能当成成功，否则调用方报出 candidate_count>0
        而 get_run 再查时一条都没有（假成功）。三个归集器共用此逻辑，
        标签词（结构化/事件/BI 指标）经 label 原样注入日志与 message。
        """
        if not records:
            return None
        try:
            self.candidate_storage.bulk_insert_candidates(records)
        except Exception as e:
            logger.error("%s候选归集落库失败: %s", label, e)
            return {
                "status": "error",
                "message": f"{label}候选落库失败（{len(records)} 条未持久化）: {e}",
            }
        return None
```

- [ ] **Step 6: 运行测试，确认 GREEN**

Run（仓库根）:
```bash
PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py::TestPersistRecordsHelper -q --no-header -p no:cacheprovider
```
Expected: **PASS**，3 passed。

- [ ] **Step 7: 跑整份测试文件，确认既有用例未受影响**

Run（仓库根）:
```bash
PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py -q --no-header -p no:cacheprovider
```
Expected: **PASS**，64 passed（既有 61 + 新增 3）。此步证明新增 helper 未破坏任何既有行为（Task 1 只加方法、尚未改调用点，既有 61 条本就该全绿）。

- [ ] **Step 8: 建议提交边界与 message（交用户执行，执行者不自动提交）**

精确 stage 本 Task 改动的 2 个文件（**禁止 `git add -A`**）：
```bash
git add apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py apps/api/tests/unit/test_semantic_asset_pipeline_structured.py
```
建议 message：
```
refactor(semantic-admin): 抽出 _persist_records 候选落库 helper + 直测

- 新增 SemanticAssetPipeline._persist_records(records, label)：空/成功→None，失败→显式 error dict（规则 14 假成功防线）
- 补 3 条直测（存储边界 patch，走真实函数体）
- 本 commit 仅加方法，调用点改写在下一 commit
```
> 注：Task 1 与 Task 2 可作为 **两个** 提交（helper 落地 / 消除重复），也可由用户合并为 **一个** 原子提交。二者皆可独立 revert。执行者只负责 stage 与验证，提交动作由用户完成。

---

## Task 2: 3 个归集器改写为调用 helper + 行为保持回归

**Files:**
- Modify: `apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py`（3 处内联落库块 → 3 行调用）
- Test: `apps/api/tests/unit/test_semantic_asset_pipeline_structured.py`（**不改**，仅作行为保持的回归网）

**Interfaces:**
- Consumes: Task 1 产出的 `self._persist_records(records, label) -> Optional[Dict[str, Any]]`（签名逐字见 Task 1）。
- Produces: 无新增对外接口；3 个 `_collect_*_candidates` 的返回结构与行为 **保持不变**（这是本 Task 的验收标准）。

- [ ] **Step 1: 改写结构化归集器的落库块**

在 `pipeline_service.py` 的 `_collect_structured_candidates` 中，把当前的内联落库块（`if records:` + 两行注释 + `try/except`，当前第 1038-1048 行）整段替换为 3 行调用。

Edit 锚点（old_string，逐字，含前置的 `warnings` 收尾与后置的 `return`）：
```python
        if records:
            # 落库失败绝不能当成成功：返回未持久化的候选会让调用方报出
            # candidate_count>0，而 get_run 再查时一条都没有（规则 14：假成功）。
            try:
                self.candidate_storage.bulk_insert_candidates(records)
            except Exception as e:
                logger.error("结构化候选归集落库失败: %s", e)
                return {
                    "status": "error",
                    "message": f"结构化候选落库失败（{len(records)} 条未持久化）: {e}",
                }
```
替换为（new_string）：
```python
        persist_err = self._persist_records(records, "结构化")
        if persist_err:
            return persist_err
```

- [ ] **Step 2: 改写事件归集器的落库块**

在 `_collect_event_candidates` 中，把内联落库块（当前第 1235-1243 行，标签 "事件"，**无** 解释性注释）替换为 3 行调用。

Edit 锚点（old_string，逐字）：
```python
        if records:
            try:
                self.candidate_storage.bulk_insert_candidates(records)
            except Exception as e:
                logger.error("事件候选归集落库失败: %s", e)
                return {
                    "status": "error",
                    "message": f"事件候选落库失败（{len(records)} 条未持久化）: {e}",
                }
```
替换为（new_string）：
```python
        persist_err = self._persist_records(records, "事件")
        if persist_err:
            return persist_err
```
> 注意：事件归集器在落库块 **之前** 有一段 `if not records: warnings.append(...)`（第 1229-1233 行），那是独立的告警逻辑，**不属于** 落库块，保持不动。

- [ ] **Step 3: 改写 BI 指标归集器的落库块**

在 `_collect_indicator_candidates` 中，把内联落库块（当前第 1334-1342 行，标签 "BI 指标"，**无** 解释性注释）替换为 3 行调用。

Edit 锚点（old_string，逐字）：
```python
        if records:
            try:
                self.candidate_storage.bulk_insert_candidates(records)
            except Exception as e:
                logger.error("BI 指标候选归集落库失败: %s", e)
                return {
                    "status": "error",
                    "message": f"BI 指标候选落库失败（{len(records)} 条未持久化）: {e}",
                }
```
替换为（new_string）：
```python
        persist_err = self._persist_records(records, "BI 指标")
        if persist_err:
            return persist_err
```
> 注意：指标归集器在落库块 **之前** 同样有一段 `if not records: warnings.append(...)`（第 1328-1332 行），保持不动。

- [ ] **Step 4: 确认再无重复的内联落库块**

Run:
```bash
grep -rn "候选归集落库失败" apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py
```
Expected: **仅 1 处** 命中，即 helper `_persist_records` 内的 `logger.error("%s候选归集落库失败: %s", label, e)`。若仍出现 "结构化候选归集落库失败"/"事件候选归集落库失败"/"BI 指标候选归集落库失败" 字面量，说明有归集器未改写干净 —— 回到 Step 1-3 修正。

- [ ] **Step 5: 行为保持回归 —— 整份测试文件全绿（不改一行测试）**

Run（仓库根）:
```bash
PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py -q --no-header -p no:cacheprovider
```
Expected: **PASS**，64 passed。
> 关键回归点：3 条既有落库失败用例 —— `TestCandidatesAreReallyPersisted::test_bulk_insert_failure_is_an_error_not_a_silent_success`（结构化，第 559 行）、`TestEventCandidateCollection` 内的落库失败用例（第 1250 行附近）、`TestIndicatorCandidateCollection` 内的落库失败用例（第 1408 行附近）—— 都在存储边界 patch `bulk_insert_candidates` 后走 `_collect_*` 全链路，会 **真实执行改写后的 helper**。它们全绿 = 三处改写的 error dict 结构、message 文案、`未持久化` 计数逐字保持。这 3 条 **不得修改**；若其中任何一条 RED，说明改写引入了行为漂移，必须修正 helper 调用而非改测试。

- [ ] **Step 6: 架构契约 lint-imports（C1-C4）全绿**

Run:
```bash
cd apps/api && uv run --frozen --no-sync lint-imports
```
Expected: 全部契约 **PASSED**，无新增违规。本重构未新增任何 import（helper 只用到已导入的 `typing` 与模块级 `logger`），故 C1-C4 应与 BASE 完全一致。

- [ ] **Step 7: 显式确认无文档同步触发（规则 12）**

逐条核对 AGENTS.md 规则 12 触发条件，确认本重构 **不触发任何一条**：
- 未新增/删除/重命名后端模块 ✓（仅在既有类内加私有方法）
- 未新增路由模块 / 未改 API 路径前缀 ✓
- 未新增架构级决策（无新基础设施/新模式/新数据流）✓ —— 这是消除重复的内部重构，非新决策
- 未新增/变更环境变量 ✓
- 未新增/变更 compose 服务或启动命令 ✓
- 存储层未新增表或字段 ✓（`bulk_insert_candidates` 签名与行为不变）
- 未改 CI workflow 或 `[tool.importlinter]` 契约 ✓

结论：**无需改文档**。`docs/03-modules/semantic_admin/DESIGN.md §4.5` 记录的归集行为不因本重构改变。在执行报告里写明「已核对规则 12，无文档同步触发」，不要留 TODO。

- [ ] **Step 8: 建议提交边界与 message（交用户执行，执行者不自动提交）**

精确 stage 本 Task 改动的 1 个文件（测试文件 Task 2 未改，若 Task 1/2 合并提交则一并 stage）：
```bash
git add apps/api/odap/biz/semantic_admin/semantic_asset_pipeline/services/pipeline_service.py
```
建议 message：
```
refactor(semantic-admin): 3 个归集器落库块改写为调用 _persist_records

- _collect_structured/_collect_event/_collect_indicator_candidates 各消除一段重复落库块
- 行为逐字保持：既有 61 条测试不改一行全绿（含 3 条落库失败显式化用例）
- lint-imports C1-C4 全绿；已核对规则 12 无文档同步触发
```

---

## 完成后（收尾）

两个 Task 均 GREEN 且用户提交后，本重构完成。可选的最终校验：

- [ ] **整份 changed-module 面回归**（与 ADR-082 终审同口径，确认无跨文件连带影响）：
  ```bash
  PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_semantic_asset_pipeline_structured.py apps/api/tests/unit/test_unified_ingest_facade.py -q --no-header -p no:cacheprovider
  ```
  Expected: 全绿（64 + 15 = 79 passed）。

- [ ] 若走 subagent-driven-development，最终 whole-branch review 只需覆盖本重构的 diff（BASE = ADR-082 提交后的 commit，HEAD = 本重构提交），review 面很小：一个 helper + 3 处 3 行调用 + 3 条直测。

---

## Self-Review

**1. Spec coverage（对照 finding (a) 与已批准设计）:**
- 抽出 `_persist_records(records, label) -> Optional[Dict]` → Task 1 Step 5 ✓
- 3 个归集器（结构化/事件/BI 指标）改写为调用 → Task 2 Step 1-3 ✓
- 空→None / 成功→None / 失败→显式 error dict → Task 1 Step 3（3 条直测）+ Step 5 实现 ✓
- 补 2-3 条直测 → Task 1 Step 3（3 条）✓
- 既有 61 条测试不改一行全绿（行为保持证据）→ Task 2 Step 5 ✓
- 离线 pytest 调用式 → Global Constraints + 每个 Step 逐字给出 ✓
- lint-imports C1-C4 复检 → Task 2 Step 6 ✓
- 执行 gated on 用户先提交 ADR-082 → Global Constraints + Task 1 Step 2 硬门禁校验 ✓
- no-commit override（执行者不提交）→ Global Constraints + Task 1/2 的 Step 8 明确「交用户执行」✓
- finding (b)/(c) 不在范围 → Global Constraints「只做 (a)」+「不得顺手改 (b)/(c)」✓

**2. Placeholder scan:** 无 TBD/TODO/"implement later"/"add error handling" 等占位。所有代码步骤含逐字代码块；所有验证步骤含精确命令与 Expected；Edit 锚点给出 old_string/new_string 逐字内容。✓

**3. Type consistency:** helper 签名 `_persist_records(self, records: List[Dict[str, Any]], label: str) -> Optional[Dict[str, Any]]` 在 Task 1 Interfaces、Task 1 Step 5 实现、Task 2 Interfaces 三处 **逐字一致**。3 个标签词 "结构化"/"事件"/"BI 指标" 在 Task 1 Step 3 测试、Task 2 Step 1-3 调用、File Structure 对照表中 **完全一致**。返回契约（None / `{"status":"error","message":...}`）全程一致，且与既有内联块逐字对齐。✓

**4. 行为保持的可靠性:** helper 的日志字符串 `"%s候选归集落库失败: %s"` 以 `label` 代入后，三处分别还原为 `"结构化候选归集落库失败: %s"` / `"事件候选归集落库失败: %s"` / `"BI 指标候选归集落库失败: %s"` —— 与 BASE 逐字相同。message f-string `f"{label}候选落库失败（{len(records)} 条未持久化）: {e}"` 同理还原。`if records:` 守卫移入 helper 的 `if not records: return None`，语义等价（空记录不落库、不报错，继续走到 `return {"status":"ok", ...}`）。✓
