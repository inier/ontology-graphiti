"""文件上传流式工具 — 分块写盘 + 大小限制。

P3-M9 整改：原先多个上传端点用 `await file.read()` 一次性读入内存，
大文件会导致内存峰值飙升甚至 OOM。本模块提供：

1. stream_upload_to_file(file, dest_path, max_size) — 分块写盘，超限即中止
2. safe_upload_size(file, max_size) — 预检 Content-Length，提前拒绝超大文件
"""

import logging
import os
from typing import Optional

from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

# 默认分块大小：1 MB（平衡 I/O 次数与内存占用）
DEFAULT_CHUNK_SIZE = 1024 * 1024


async def stream_upload_to_file(
    file: UploadFile,
    dest_path: str,
    *,
    max_size: int,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> int:
    """将上传文件分块写入 dest_path，返回总字节数。

    写入过程中累计大小，超过 max_size 立即删除已写入的部分并抛 400。

    Args:
        file: Starlette UploadFile
        dest_path: 目标文件路径（调用方需确保目录存在、路径安全）
        max_size: 最大允许字节数
        chunk_size: 每次写入的块大小

    Returns:
        实际写入的总字节数

    Raises:
        HTTPException(400): 文件超过 max_size
    """
    total = 0
    try:
        with open(dest_path, "wb") as f:
            async for chunk in file.chunks(chunk_size):
                total += len(chunk)
                if total > max_size:
                    f.close()
                    try:
                        os.unlink(dest_path)
                    except OSError:
                        pass
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"File too large: exceeds {max_size} bytes limit. "
                            f"Uploaded {total} bytes so far."
                        ),
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        # 清理半成品文件
        try:
            if os.path.exists(dest_path):
                os.unlink(dest_path)
        except OSError:
            pass
        raise
    return total


def check_upload_size(file: UploadFile, max_size: int) -> None:
    """预检 UploadFile.size（Content-Length），提前拒绝超大文件。

    若 file.size 为 None（chunked transfer encoding），跳过预检，
    由后续 stream_upload_to_file 或 file.read() 后的检查兜底。

    Args:
        file: Starlette UploadFile
        max_size: 最大允许字节数

    Raises:
        HTTPException(400): Content-Length 超过 max_size
    """
    declared = getattr(file, "size", None)
    if declared is not None and declared > max_size:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File too large: Content-Length {declared} exceeds "
                f"maximum {max_size} bytes."
            ),
        )
