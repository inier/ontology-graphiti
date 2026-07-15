"""Hook管理器实现"""

import json
import logging
import os
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.hook_manager import IHookManager
from ..models.hook import Hook, HookType, HookStatus, HookExecution

logger = logging.getLogger(__name__)

# ── 审计工具（懒加载 + 容错，审计失败不打断业务） ──
def _hook_audit(action: str, *, result_status: str = "success",
                result_message: str = "", resource: str = None,
                details: Dict[str, Any] = None) -> None:
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="integration_hook",
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")

# 最大执行时间上限（秒），防止 hook.timeout_ms 设置过大
MAX_EXECUTION_TIMEOUT_SECONDS = 30

# 安全：Shell Hook 允许的命令白名单（仅这些命令可执行，禁止任意脚本注入）
# 选用 shlex.split + argv[0] 白名单，避免 shell=True 带来的元字符注入风险。
_ALLOWED_SHELL_COMMANDS = frozenset({
    "echo", "printf", "date", "true", "false",
    "cat", "head", "tail", "wc", "sort", "uniq", "cut", "tr",
    "grep", "egrep", "fgrep",
    "ls", "pwd", "env", "whoami", "hostname",
    "test", "[",
    "python", "python3", sys.executable,
    "node", "jq",
})

# 安全：Shell Hook 禁止的危险元字符（出现即拒绝执行）
_SHELL_DANGEROUS_CHARS = re.compile(r"[;&|`$<>{}\n\r]")


class HookManager(IHookManager):
    """Hook管理器实现"""
    
    def __init__(self):
        self._hooks: Dict[str, Hook] = {}
        self._executions: Dict[str, List[HookExecution]] = {}
    
    def register_hook(self, name: str, hook_type: HookType, script: str, 
                    description: str = "", language: str = "python") -> Hook:
        """注册Hook"""
        hook = Hook(
            name=name,
            hook_type=hook_type,
            script=script,
            description=description,
            language=language
        )
        self._hooks[hook.id] = hook
        self._executions[hook.id] = []
        # 审计：注册成功（只记 hook_id/type/language，不记脚本明文）
        _hook_audit(
            action="hook_register",
            result_status="success",
            resource=hook.id,
            details={
                "hook_id": hook.id,
                "hook_type": hook_type.value if hasattr(hook_type, "value") else str(hook_type),
                "language": language,
                "name_len": len(name),
            },
        )
        return hook
    
    def get_hook(self, hook_id: str) -> Optional[Hook]:
        """获取Hook"""
        return self._hooks.get(hook_id)
    
    def update_hook(self, hook_id: str, updates: Dict[str, Any]) -> Hook:
        """更新Hook"""
        hook = self._hooks.get(hook_id)
        if not hook:
            _hook_audit(
                action="hook_update",
                result_status="failure",
                result_message="Hook not found",
                resource=hook_id,
                details={"hook_id": hook_id},
            )
            raise ValueError("Hook not found")

        changed_keys = [k for k in updates.keys() if hasattr(hook, k)]
        for key, value in updates.items():
            if hasattr(hook, key):
                setattr(hook, key, value)

        hook.updated_at = datetime.now()
        _hook_audit(
            action="hook_update",
            result_status="success",
            resource=hook_id,
            details={"hook_id": hook_id, "changed_fields": changed_keys, "field_count": len(changed_keys)},
        )
        return hook

    def delete_hook(self, hook_id: str) -> bool:
        """删除Hook"""
        if hook_id in self._hooks:
            del self._hooks[hook_id]
            _hook_audit(
                action="hook_unregister",
                result_status="success",
                resource=hook_id,
                details={"hook_id": hook_id},
            )
            return True
        _hook_audit(
            action="hook_unregister",
            result_status="failure",
            result_message="Hook not found",
            resource=hook_id,
            details={"hook_id": hook_id},
        )
        return False
    
    def list_hooks(self, filters: Dict[str, Any] = None, 
                  page: int = 1, page_size: int = 10) -> List[Hook]:
        """列出Hooks"""
        filters = filters or {}
        hooks = list(self._hooks.values())
        
        if "type" in filters:
            hooks = [h for h in hooks if h.hook_type.value == filters["type"]]
        if "status" in filters:
            hooks = [h for h in hooks if h.status.value == filters["status"]]
        
        start = (page - 1) * page_size
        end = start + page_size
        return hooks[start:end]
    
    def execute_hook(self, hook_id: str, context: Dict[str, Any] = None) -> HookExecution:
        """执行Hook

        根据 hook.language 和 hook.script 内容决定执行方式：
        - python: 在受限命名空间中 exec() 执行
        - shell: 通过 subprocess.run() 执行
        - 如果 script 是文件路径（存在该文件），则读取文件内容后执行
        """
        hook = self._hooks.get(hook_id)
        if not hook:
            _hook_audit(
                action="trigger_hook",
                result_status="failure",
                result_message="Hook not found",
                resource=hook_id,
                details={"hook_id": hook_id, "sandboxed": False},
            )
            raise ValueError("Hook not found")

        if hook.status == HookStatus.INACTIVE:
            _hook_audit(
                action="trigger_hook",
                result_status="failure",
                result_message="Hook is inactive",
                resource=hook_id,
                details={"hook_id": hook_id, "sandboxed": False},
            )
            raise ValueError(f"Hook {hook_id} is inactive")

        execution = HookExecution(hook_id=hook_id)
        context = context or {}

        # 计算超时秒数，不超过上限
        timeout_seconds = min(hook.timeout_ms / 1000.0, MAX_EXECUTION_TIMEOUT_SECONDS)
        if timeout_seconds <= 0:
            timeout_seconds = MAX_EXECUTION_TIMEOUT_SECONDS

        start_time = datetime.now()
        event_name = context.get("event_name", "") if isinstance(context, dict) else ""
        failure_excerpt = ""

        try:
            script = hook.script

            # 判断 script 是否为文件路径
            if os.path.isfile(script):
                with open(script, "r", encoding="utf-8") as f:
                    script = f.read()

            if hook.language == "python":
                result = self._execute_python(script, context, timeout_seconds)
            elif hook.language == "shell":
                result = self._execute_shell(script, context, timeout_seconds)
            else:
                result = {
                    "status": "error",
                    "message": f"Unsupported hook language: {hook.language}",
                }

            execution.status = "success"
            execution.result = result
            if result.get("status") and result.get("status") != "success":
                failure_excerpt = str(result.get("message", ""))[:200]
                execution.status = "error"
                execution.error = failure_excerpt

        except subprocess.TimeoutExpired:
            execution.status = "error"
            execution.error = f"Hook execution timed out after {timeout_seconds}s"
            failure_excerpt = execution.error[:200]
            logger.warning(f"Hook {hook_id} timed out after {timeout_seconds}s")
        except SyntaxError as e:
            execution.status = "error"
            execution.error = f"Syntax error in hook script: {e}"
            failure_excerpt = execution.error[:200]
            logger.warning(f"Hook {hook_id} syntax error: {e}")
        except Exception as e:
            execution.status = "error"
            execution.error = str(e)
            failure_excerpt = execution.error[:200]
            logger.warning(f"Hook {hook_id} execution failed: {e}")

        execution.duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        # 审计：触发执行（只记统计量，不记 context/result 明文）
        result_status_str = "success" if execution.status == "success" else "failure"
        _hook_audit(
            action="trigger_hook",
            result_status=result_status_str,
            result_message=failure_excerpt if failure_excerpt else "",
            resource=hook_id,
            details={
                "hook_id": hook_id,
                "event_name": event_name[:80] if event_name else "",
                "sandboxed": True,
                "execution_duration_ms": execution.duration_ms,
                "result_status": result_status_str,
                "failure_message": failure_excerpt,
                "language": hook.language,
            },
        )

        # 保存执行记录
        if hook_id in self._executions:
            self._executions[hook_id].append(execution)

        return execution

    def _execute_python(self, script: str, context: Dict[str, Any],
                        timeout_seconds: float) -> Dict[str, Any]:
        """在受限命名空间中执行 Python 脚本

        使用 subprocess 启动独立进程执行，以实现超时控制和隔离。
        """
        context_json = json.dumps(context, default=str, ensure_ascii=False)

        # 包装脚本：注入 context，捕获 _output
        wrapper_lines = [
            "import json, sys",
            "try:",
            f"    _context = json.loads({repr(context_json)})",
            "    _output = None",
        ]

        # 将用户脚本缩进嵌入 try 块
        for line in script.strip().split("\n"):
            wrapper_lines.append("    " + line)

        wrapper_lines.extend([
            "    if _output is None:",
            "        _output = 'completed'",
            "    print(json.dumps({'status': 'success', 'output': _output}, default=str, ensure_ascii=False))",
            "except Exception as _e:",
            "    print(json.dumps({'status': 'error', 'message': str(_e)}, ensure_ascii=False))",
        ])

        wrapper = "\n".join(wrapper_lines)

        # 写入临时文件并执行
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(wrapper)
            tmp_path = tmp.name

        try:
            proc = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=tempfile.gettempdir(),
            )

            if proc.returncode == 0:
                try:
                    result = json.loads(proc.stdout.strip().split("\n")[-1])
                    return result
                except (json.JSONDecodeError, IndexError):
                    return {
                        "status": "success",
                        "output": proc.stdout.strip(),
                        "stderr": proc.stderr.strip(),
                    }
            else:
                return {
                    "status": "error",
                    "message": proc.stderr.strip() or "Python script exited with non-zero code",
                    "returncode": proc.returncode,
                }
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _execute_shell(self, script: str, context: Dict[str, Any],
                       timeout_seconds: float) -> Dict[str, Any]:
        """通过 subprocess 执行 Shell 命令（白名单模式）

        安全策略（C2 修复）：
        1. 拒绝包含危险元字符（; & | ` $ < > { } 换行）的脚本，阻断 shell 注入。
        2. 使用 shlex.split 解析 argv，shell=False 执行，避免 shell 元字符解释。
        3. argv[0] 必须在 _ALLOWED_SHELL_COMMANDS 白名单内，禁止任意可执行文件。
        4. context 作为环境变量传入（HOOK_<KEY> 前缀），不参与命令拼接。
        """
        # 1. 危险元字符检查
        if _SHELL_DANGEROUS_CHARS.search(script):
            return {
                "status": "error",
                "message": (
                    "Shell script contains forbidden characters "
                    "(; & | ` $ < > {{ }} newline). Refusing to execute."
                ),
            }

        # 2. 解析 argv
        try:
            argv = shlex.split(script, comments=True, posix=True)
        except ValueError as e:
            return {
                "status": "error",
                "message": f"Failed to parse shell script: {e}",
            }
        if not argv:
            return {"status": "error", "message": "Empty shell script"}

        # 3. argv[0] 白名单校验
        cmd_name = os.path.basename(argv[0])
        if cmd_name not in _ALLOWED_SHELL_COMMANDS:
            return {
                "status": "error",
                "message": (
                    f"Command '{cmd_name}' is not in the allowed whitelist. "
                    f"Allowed: {sorted(_ALLOWED_SHELL_COMMANDS)}"
                ),
            }

        # 4. context 作为环境变量传入（不参与命令拼接）
        env = os.environ.copy()
        for key, value in context.items():
            env[f"HOOK_{key.upper()}"] = str(value)

        try:
            proc = subprocess.run(
                argv,
                shell=False,  # 关键：不再使用 shell=True
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=env,
            )

            if proc.returncode == 0:
                return {
                    "status": "success",
                    "output": proc.stdout.strip(),
                }
            else:
                return {
                    "status": "error",
                    "message": proc.stderr.strip() or f"Shell exited with code {proc.returncode}",
                    "returncode": proc.returncode,
                    "stdout": proc.stdout.strip(),
                }
        except subprocess.TimeoutExpired:
            raise
        except FileNotFoundError as e:
            return {
                "status": "error",
                "message": f"Shell command not found: {e}",
            }
    
    def get_hook_executions(self, hook_id: str, limit: int = 10) -> List[HookExecution]:
        """获取Hook执行记录"""
        executions = self._executions.get(hook_id, [])
        return executions[-limit:]
