"""
图谱模块共享工具

提供 _run_async 等跨模块使用的工具函数，避免循环导入。
"""

import asyncio
import concurrent.futures


def _run_async(coro):
    """在同步上下文中运行异步协程"""
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result(timeout=60)
    except RuntimeError:
        return asyncio.run(coro)
