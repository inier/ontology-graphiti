"""graph_viewer 域 —— 图谱浏览模块。

含 api/routes.py。补常规包 __init__.py 以恢复 grimp / import-linter 静态可见性
（此前为 PEP 420 命名空间包，且因缺 __init__.py 也导致其 api/ 子包被孤立）。
不加 eager 导入。
"""
