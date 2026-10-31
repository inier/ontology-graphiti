"""上传文件解析（纯函数，无 IO、无网络、无 HTTP 依赖）。

从 `odap/tasks.py` 抽出的原因：解析口径（支持哪些格式、如何计数）与任务编排
（落库、失败翻译）变化原因不同，且同文件已超出单文件行数上限。

失败语义：不支持的扩展名/内容非法一律抛 `ValueError`（带具体扩展名），
**不返回空结果冒充成功**（SPEC §10 禁止伪实现）。
"""

from __future__ import annotations

import io
import json
from typing import Any, Dict

import pandas as pd

SUPPORTED_EXTENSIONS = (".json", ".csv", ".txt")


def parse_uploaded_file(file_content: bytes, file_extension: str) -> Dict[str, Any]:
    """按扩展名解析上传文件，返回可落库的解析摘要。

    Raises:
        ValueError: 不支持的扩展名 / 内容非法（显式失败，不返回空结果冒充成功）。
    """
    ext = (file_extension or "").lower()
    if ext == ".json":
        data = json.loads(file_content.decode("utf-8"))
        if isinstance(data, dict):
            return {"format": "json", "json_keys": list(data.keys()), "item_count": 1}
        return {"format": "json", "json_keys": [], "item_count": len(data)}
    if ext == ".csv":
        df = pd.read_csv(io.StringIO(file_content.decode("utf-8")))
        return {
            "format": "csv",
            "csv_rows": int(len(df)),
            "csv_columns": [str(c) for c in df.columns],
            "item_count": int(len(df)),
        }
    if ext == ".txt":
        lines = file_content.decode("utf-8").splitlines()
        return {"format": "txt", "text_lines": len(lines), "item_count": len(lines)}
    raise ValueError(
        f"unsupported file extension: {file_extension!r} (支持 {'/'.join(SUPPORTED_EXTENSIONS)})"
    )


__all__ = ["parse_uploaded_file", "SUPPORTED_EXTENSIONS"]
