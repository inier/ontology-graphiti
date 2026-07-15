"""沙箱实现 - 使用 subprocess 隔离执行代码"""

import logging
import subprocess
import sys
import tempfile
import os
from typing import Dict, Any, Optional
from datetime import datetime
from ..interfaces.sandbox import ISandbox
from ..models.sandbox import SandboxConfig, SandboxResult

logger = logging.getLogger(__name__)


class Sandbox(ISandbox):
    """沙箱实现 - 使用 subprocess 隔离执行代码"""

    def __init__(self):
        self._sandboxes: Dict[str, SandboxConfig] = {}
        self._results: Dict[str, SandboxResult] = {}

    def create_sandbox(self, config: SandboxConfig) -> SandboxConfig:
        """创建沙箱"""
        self._sandboxes[config.id] = config
        return config

    def execute(self, sandbox_id: str, code: str, timeout_ms: int = 5000) -> SandboxResult:
        """在沙箱中执行代码 - 使用 subprocess 隔离执行"""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            raise ValueError("Sandbox not found")

        result = SandboxResult(sandbox_config_id=sandbox_id)

        # 应用 SandboxConfig 中的超时限制
        effective_timeout_ms = min(timeout_ms, sandbox.max_execution_time_ms)
        timeout_sec = effective_timeout_ms / 1000.0

        # 将代码写入临时文件
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(code)
                tmp_path = tmp.name
        except OSError as e:
            result.status = "error"
            result.error = f"Failed to create temp file: {e}"
            self._results[result.id] = result
            return result

        try:
            start_time = datetime.now()

            # 构建 subprocess 命令
            cmd = [sys.executable, tmp_path]

            # 设置环境变量：限制资源
            env = os.environ.copy()
            if not sandbox.network_enabled:
                # 禁用网络相关环境变量（提示性，非强制）
                env.pop("HTTP_PROXY", None)
                env.pop("HTTPS_PROXY", None)
                env.pop("http_proxy", None)
                env.pop("https_proxy", None)

            # 使用 subprocess 执行，设置超时
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec if timeout_sec > 0 else None,
                env=env,
                # 限制：不使用 shell，隔离执行
                shell=False,
            )

            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            result.execution_time_ms = execution_time_ms

            if proc.returncode == 0:
                result.status = "success"
                result.output = proc.stdout
            else:
                result.status = "error"
                result.output = proc.stdout
                result.error = proc.stderr or f"Process exited with code {proc.returncode}"

        except subprocess.TimeoutExpired:
            result.status = "error"
            result.error = f"Execution timed out after {effective_timeout_ms}ms"
            result.execution_time_ms = effective_timeout_ms

        except Exception as e:
            result.status = "error"
            result.error = str(e)

        finally:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        self._results[result.id] = result
        return result

    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """销毁沙箱"""
        if sandbox_id in self._sandboxes:
            del self._sandboxes[sandbox_id]
            return True
        return False

    def get_sandbox_status(self, sandbox_id: str) -> Dict[str, Any]:
        """获取沙箱状态"""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            return {"status": "not_found"}

        return {
            "sandbox_id": sandbox.id,
            "name": sandbox.name,
            "max_memory_mb": sandbox.max_memory_mb,
            "max_cpu_percent": sandbox.max_cpu_percent,
            "network_enabled": sandbox.network_enabled,
            "filesystem_enabled": sandbox.filesystem_enabled
        }
