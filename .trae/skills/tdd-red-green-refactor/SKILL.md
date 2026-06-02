---
name: tdd-red-green-refactor
description: TDD 红绿重构循环。在 ODAP 项目中按 Red-Green-Refactor 流程编写测试和实现代码，严格遵循 AGENTS.md 中的测试规则（新增模块必测、tmp_path fixture、HTTPException 透传等）。
compatibility: Requires Python 3.10+ and pytest
metadata:
  author: odap-project
  source: AGENTS.md testing-rules
---

# TDD 红绿重构循环

在 ODAP 项目中按 **Red → Green → Refactor** 循环编写新功能或修复 bug。

## 适用场景

- 新增 biz 模块（按 AGENTS.md "新增模块必须同步新增测试文件"）
- 新增 SQLite 存储层（必须用 `tmp_path` 真实 DB，不用 MagicMock）
- 新增 FastAPI 路由（必须测试 HTTP 状态码映射）
- 新增服务层方法（必须测试 Dict[str, Any] 返回值）
- 修复 bug（先写能复现 bug 的失败测试）

## 用户输入

$ARGUMENTS

## 流程

### 🔴 Step 1: Red — 写失败测试

1. **识别目标**：明确要实现什么功能。读取相关的 plan.md/spec.md/接口契约。
2. **找到测试文件位置**：
   - 单元测试：`tests/unit/test_{module}.py`
   - 集成测试：`tests/integration/test_{module}.py`（需 Neo4j+MongoDB）
   - 文件名必须与 `odap/biz/{领域}/{模块名}/` 路径对应
3. **选择测试分层**（按 AGENTS.md "每个模块必须覆盖的测试点"）：

| 层 | 必测场景 |
|---|---------|
| storage/ | CRUD 全流程、get 不存在返回 None、delete 不存在返回 False、JSON 字段序列化/反序列化、非法 JSON 容错 |
| models/ | 必填字段验证、默认值、容器字段 `default_factory`、Enum 值 |
| services/ | 成功返回扁平 dict、错误返回 `{"status": "error"}`、类型转换 (Enum→.value, datetime→.isoformat) |
| routes/ | HTTP 状态码映射、`except HTTPException: raise` 透传、404/400/500 场景 |

4. **编写测试**：
   - 使用 `pytest` fixture 级联：`mock_storage → xxx_manager`，通过 `patch()` 替换 Storage 类
   - 使用工厂函数：`_make_xxx(**overrides)` 构造测试数据
   - 使用 `TestSQLiteXxxStorage`、`TestXxxService`、`TestXxxSchemas` 按层分组
   - SQLite 存储层用 `tmp_path` fixture 真实 DB；非存储层用 MagicMock
5. **运行测试确认失败**：
   ```bash
   pytest tests/unit/test_{module}.py -v
   ```
   必须看到 `FAILED` 或 import error，**不能跳过这一步**。

### 🟢 Step 2: Green — 最小实现

1. **实现最小代码**让测试通过：
   - 不要过度设计、不要添加测试未要求的功能
   - 严格遵守 AGENTS.md 的 6 层结构（`api/services/impl/interfaces/models/storage`）
   - 调用链：`routes.py → services/ → impl/ → storage/`，禁止跨层调用
2. **再次运行测试**确认通过：
   ```bash
   pytest tests/unit/test_{module}.py -v
   ```
3. **运行全部单元测试**确保没有回归：
   ```bash
   pytest tests/unit/ -v
   ```

### 🔵 Step 3: Refactor — 重构

1. **检查代码异味**：
   - 重复代码
   - 过长函数（>50 行考虑拆分）
   - 魔法数字/字符串（提取为常量）
   - 缺少类型注解
2. **保持测试通过**：每次小步重构后运行 `pytest tests/unit/ -v`
3. **运行 lint**：
   ```bash
   # Python
   ruff check odap/
   # Frontend
   cd frontend && npm run lint && npm run typecheck
   ```

## ODAP 特定约束（必须遵守）

1. **路由层错误处理**：
   ```python
   except HTTPException:
       raise  # 必须透传
   except Exception as e:
       raise HTTPException(status_code=500, detail=str(e))
   ```
2. **服务层返回值**：必须返回 `Dict[str, Any]`，**不直接返回 Pydantic 模型**
3. **存储层**：每次 `sqlite3.connect()` → 用完 `conn.close()`，**无连接池**
4. **领域模型**：
   - Enum 必须 `(str, Enum)` 双继承
   - 容器字段必须 `Field(default_factory=list)`，不要用 `= []`
   - datetime 用 `datetime.now`，自动生成用 `uuid.uuid4()`
5. **延迟导入**：fixture 内部 `from odap.xxx import`，避免模块级导入失败
6. **外部依赖 skip**：依赖 graphiti-core/openharness 的测试，模块级 `try/except` + `pytest.skip()`

## 完成检查

- [ ] Red 阶段：测试已写且确认失败
- [ ] Green 阶段：实现完成且 `pytest tests/unit/ -v` 全部通过
- [ ] Refactor 阶段：代码已优化且 lint 通过
- [ ] 没有回归：`pytest tests/unit/ -v` 全部通过
- [ ] 代码已提交（参考 `tdd-git-commit`）

## 输出

提供以下总结：
- 实现的文件路径
- 测试覆盖的层（storage/models/services/routes）
- 关键设计决策
- 下一步建议（如有）
