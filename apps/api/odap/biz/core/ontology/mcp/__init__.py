"""MCP 适配（ontology 侧）—— 语义检索工具暴露。

含 semantic_retrieval_tools.py。历史上缺 __init__.py 而以 PEP 420 命名空间包
形式存在，导致 grimp / import-linter 无法索引本目录；补常规包 __init__.py 后
恢复静态可见性。刻意不加 eager 导入，避免级联与循环（参见 design/__init__.py 说明）。
"""
