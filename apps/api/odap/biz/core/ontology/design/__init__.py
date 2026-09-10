"""L1 Design — 本体设计层（ADR-068 四层架构之一）。

子模块:
- contract/          — OntologyDesignContract 只读契约（跨边界唯一合法入口，ADR-071）
- schema/            — 领域 Schema（document / domain）
- model/             — 模型服务与存储
- version/           — 版本管理
- services/          — 设计层服务（version_service / search_service / edit_lock_service）
- engine/            — 设计引擎（含 SHACL/OWL 治理路由）
- ingestion/         — 摄入路由
- ingestion_split/   — 文档 IO 与新闻/自由文本摄入器
- storage/           — 设计层 SQLite 存储
- interfaces/        — 抽象基类
- impl/              — 接口实现
- mock_data/         — 模拟数据生成
- events.py          — 设计层事件

设计约定（重要）：
    本文件刻意保持**无 eager 导入**（仅 docstring）。历史上 design/ 曾是
    PEP 420 命名空间包（缺 __init__.py），导致 grimp / import-linter 静态
    扫描无法进入本子树——整个 L1 设计层对架构契约（C1/C2/C3）不可见。
    补上常规包 __init__.py 后，静态分析恢复覆盖。为避免重蹈 T1 覆辙
    （包 __init__ eager 导入服务层引发级联与循环），此处**不得**加入
    `from .xxx import ...` 之类的再导出；外部一律经
    `odap.biz.core.ontology.public` 门面或直接子模块路径访问。
"""
