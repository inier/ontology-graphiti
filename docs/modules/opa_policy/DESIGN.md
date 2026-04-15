# OPA 策略管理模块设计文档

> **优先级**: P0 | **相关 ADR**: ADR-003, ADR-009

## 1. 模块概述

### 1.1 模块定位

`opa_policy` 是系统的策略治理引擎，负责权限校验、规则执行、合规检查和 Fail-Close 安全机制。

### 1.2 核心职责

| 职责 | 描述 |
|------|------|
| 权限校验 | 验证 Agent/用户是否有权执行特定操作 |
| 规则执行 | 执行业务规则（如禁止攻击民用设施） |
| 合规检查 | 确保操作符合法规要求 |
| Fail-Close | 不了解的操作默认拒绝 |
| 审计追溯 | 记录所有策略检查结果 |

---

## 2. 接口设计

### 2.1 OPAManager 主接口

```python
# core/opa_policy/manager.py
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from datetime import datetime

class PolicyResult(BaseModel):
    """策略检查结果"""
    allowed: bool
    reason: Optional[str] = None
    policy_package: str
    evaluated_at: datetime = Field(default_factory=datetime.now)
    execution_time_ms: float

class OPAManager:
    """OPA 策略管理器"""

    async def initialize(self) -> None: ...
    async def health_check(self) -> bool: ...

    async def check(
        self,
        policy_package: str,
        input_data: Dict[str, Any]
    ) -> PolicyResult: ...

    async def check_and_raise(
        self,
        policy_package: str,
        input_data: Dict[str, Any]
    ) -> None: ...

    async def bulk_check(
        self,
        requests: List[Tuple[str, Dict[str, Any]]]
    ) -> List[PolicyResult]: ...

    async def reload_policies(self) -> bool: ...
```

### 2.2 领域领域策略接口

```python
# core/opa_policy/domain_policies.py

class DomainOPAManager(OPAManager):
    """领域领域 OPA 管理器"""

    async def check_attack(
        self,
        commander_id: str,
        target: Dict[str, Any],
        weapon_type: str,
        context: Dict[str, Any]
    ) -> PolicyResult: ...

    async def check_intelligence_access(
        self,
        agent_id: str,
        intelligence_type: str,
        clearance_level: int
    ) -> PolicyResult: ...
```

---

## 3. 策略包设计

### 3.1 策略包结构

```
policies/
├── attack/
│   ├── allow.rego
│   ├── deny.rego
│   └── test.rego
├── intelligence/
│   ├── allow.rego
│   └── classify.rego
├── agent/
│   ├── commander.rego
│   ├── intelligence.rego
│   └── operations.rego
└── common/
    ├── default.rego
    └── input.rego
```

### 3.2 核心策略示例

```rego
# policies/attack/allow.rego
package policies.attack

import future.keywords.if

allow if {
    input.action == "attack_target"
    input.commander_id != ""
    input.target != {}
    input.weapon_type != ""
    not is_protected_target(input.target)
}

is_protected_target(target) if {
    target.category == "civilian"
} if {
    target.category == "medical"
} if {
    target.category == "historical"
}
```

```rego
# policies/common/default.rego
package policies.common

import future.keywords.if

default allow = false

allow if {
    input.user.role == "admin"
}
```

---

## 4. 数据模型

```python
# core/opa_policy/models.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class Target(BaseModel):
    """打击目标"""
    id: str
    target_type: str
    category: str
    confirmation_level: str = "unconfirmed"
    distance: float = 0.0
    protected_status: bool = False

class AttackInput(BaseModel):
    """打击操作输入"""
    action: str = "attack_target"
    commander_id: str
    target: Target
    weapon_type: str
    timestamp: datetime = Field(default_factory=datetime.now)

class RulesOfEngagement(BaseModel):
    """交战规则"""
    start_hour: int = 0
    end_hour: int = 24
    restricted: bool = False
    protected_categories: List[str] = Field(default_factory=list)
```

---

## 5. 核心实现

```python
# core/opa_policy/manager.py
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

class OPAManagerImpl(OPAManager):
    """OPA 策略管理器实现"""

    async def initialize(self) -> None:
        logger.info(f"Initializing OPA Manager: {self.opa_url}")
        try:
            from opa import OPAClient
            self._client = OPAClient(base_url=self.opa_url)
        except ImportError:
            logger.warning("opa-python-sdk not found, using HTTP")
            self._client = None

    async def health_check(self) -> bool:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.opa_url}/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error(f"OPA health check failed: {e}")
            return False

    async def check(
        self,
        policy_package: str,
        input_data: Dict[str, Any]
    ) -> PolicyResult:
        """策略检查（Fail-Close）"""
        start_time = datetime.now()
        try:
            if self._client:
                result = await self._client.check(policy_package, input_data)
            else:
                result = await self._http_check(policy_package, input_data)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            return PolicyResult(
                allowed=result.get("allow", False),
                reason=result.get("reason"),
                policy_package=policy_package,
                execution_time_ms=execution_time
            )
        except Exception as e:
            logger.error(f"OPA check failed, fail-close: {e}")
            return PolicyResult(
                allowed=False,
                reason=f"Fail-close: {str(e)}",
                policy_package=policy_package,
                execution_time_ms=0
            )

    async def _http_check(
        self,
        policy_package: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """HTTP 调用 OPA"""
        import aiohttp
        url = f"{self.opa_url}/v1/data/{policy_package.replace('.', '/')}"
        payload = {"input": input_data}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                return {"allow": result.get("result", False)}
```

---

## 6. 配置示例

```yaml
# config/opa_policy.yaml
opa_policy:
  opa:
    url: "http://localhost:8181"

  cache:
    enabled: true
    ttl_seconds: 60

  tool_policy_mappings:
    attack_target: "policies/attack/allow"
    command_unit: "policies/command/allow"
    radar_search: "policies/intelligence/allow"

  fail_close:
    enabled: true
```

---

## 7. 错误处理

```python
# core/opa_policy/exceptions.py

class OPAPolicyDenied(Exception):
    def __init__(self, policy: str, input_data: dict, reason: str = None):
        self.policy = policy
        self.input_data = input_data
        self.reason = reason
        super().__init__(f"OPA denied: {policy} - {reason}")
```

---

## 8. 策略调试与沙盒环境

### 8.1 策略沙盒设计
```python
# core/opa_policy/debug_tool.py
import json
from typing import Dict, Any, List
import rego

class PolicySandbox:
    """策略沙盒环境"""
    
    def __init__(self):
        self.policy_cache = {}
        
    async def debug_policy(self, policy_code: str, test_cases: List[Dict]) -> Dict:
        """调试策略"""
        results = []
        
        for test in test_cases:
            # 1. 执行策略
            result = await self.evaluate_policy(policy_code, test["input"])
            
            # 2. 记录执行路径
            execution_trace = self.capture_trace(result)
            
            # 3. 可视化展示
            visualization = self.generate_visual_trace(execution_trace)
            
            results.append({
                "test_case": test["name"],
                "expected": test["expected"],
                "actual": result,
                "trace": execution_trace,
                "visualization": visualization,
                "passed": result == test["expected"]
            })
            
        return {
            "summary": f"{sum(r['passed'] for r in results)}/{len(results)} passed",
            "details": results
        }
    
    async def evaluate_policy(self, policy_code: str, input_data: Dict[str, Any]) -> Dict:
        """评估策略"""
        # 使用 rego 库执行策略
        import rego
        module = rego.parse(policy_code)
        result = module.evaluate(input_data)
        return result
    
    def capture_trace(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """捕获执行路径"""
        return {
            "decision_path": result.get("decision_path", []),
            "rule_activations": result.get("rule_activations", []),
            "variables": result.get("variables", {}),
            "execution_time_ms": result.get("execution_time_ms", 0)
        }
    
    def generate_visual_trace(self, trace: Dict[str, Any]) -> Dict[str, Any]:
        """生成可视化跟踪"""
        return {
            "type": "decision_tree",
            "nodes": [
                {"id": "start", "label": "开始"},
                {"id": "rules", "label": f"激活规则: {len(trace['rule_activations'])}"},
                {"id": "decision", "label": f"决策: {trace.get('decision', 'unknown')}"}
            ],
            "edges": [
                {"from": "start", "to": "rules"},
                {"from": "rules", "to": "decision"}
            ]
        }
```

### 8.2 调试工具接口
```python
# core/opa_policy/debug_api.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/debug", tags=["opa_debug"])

class TestCase(BaseModel):
    name: str
    input: Dict[str, Any]
    expected: Dict[str, Any]

class DebugRequest(BaseModel):
    policy_code: str
    test_cases: List[TestCase]

@router.post("/policy")
async def debug_policy(request: DebugRequest):
    """调试策略接口"""
    sandbox = PolicySandbox()
    result = await sandbox.debug_policy(request.policy_code, request.test_cases)
    return {
        "status": "success",
        "data": result
    }

@router.get("/visualize/{policy_id}")
async def visualize_policy(policy_id: str, input_json: str):
    """可视化策略执行"""
    try:
        input_data = json.loads(input_json)
        # 获取策略代码
        policy_code = await get_policy_by_id(policy_id)
        sandbox = PolicySandbox()
        result = await sandbox.evaluate_policy(policy_code, input_data)
        trace = sandbox.capture_trace(result)
        visualization = sandbox.generate_visual_trace(trace)
        return visualization
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 8.3 测试用例管理
```python
# core/opa_policy/test_manager.py
class TestCaseManager:
    """测试用例管理器"""
    
    def __init__(self):
        self.test_suites = {}
        
    def create_test_suite(self, name: str, description: str = ""):
        """创建测试套件"""
        self.test_suites[name] = {
            "description": description,
            "test_cases": [],
            "created_at": datetime.now()
        }
        return name
    
    def add_test_case(self, suite_name: str, name: str, 
                     input_data: Dict[str, Any], expected: Dict[str, Any]):
        """添加测试用例"""
        if suite_name not in self.test_suites:
            raise ValueError(f"Test suite {suite_name} not found")
        
        test_case = {
            "name": name,
            "input": input_data,
            "expected": expected
        }
        self.test_suites[suite_name]["test_cases"].append(test_case)
    
    def get_builtin_suites(self) -> Dict[str, List[Dict]]:
        """获取内置测试套件"""
        return {
            "attack_policy": [
                {
                    "name": "civilian_target_denied",
                    "input": {
                        "action": "attack_target",
                        "commander_id": "cmd_001",
                        "target": {"category": "civilian", "type": "building"},
                        "weapon_type": "missile"
                    },
                    "expected": {"allow": False, "reason": "civilian target"}
                },
                {
                    "name": "military_target_allowed",
                    "input": {
                        "action": "attack_target",
                        "commander_id": "cmd_001",
                        "target": {"category": "military", "type": "radar"},
                        "weapon_type": "missile"
                    },
                    "expected": {"allow": True}
                }
            ]
        }
```

## 9. 性能优化

### 9.1 策略预编译缓存
```python
# core/opa_policy/optimizer.py
import hashlib
import pickle
from typing import Dict, Any

class PolicyOptimizer:
    """策略优化器"""
    
    def __init__(self):
        self.compiled_cache = {}
        self.hit_count = 0
        self.miss_count = 0
        
    def compile_policy(self, policy_code: str) -> Any:
        """预编译策略"""
        cache_key = hashlib.md5(policy_code.encode()).hexdigest()
        
        if cache_key in self.compiled_cache:
            self.hit_count += 1
            return self.compiled_cache[cache_key]
        
        self.miss_count += 1
        # 编译策略
        import rego
        compiled = rego.compile(policy_code)
        
        # 缓存
        self.compiled_cache[cache_key] = compiled
        return compiled
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total if total > 0 else 0
        return {
            "cache_size": len(self.compiled_cache),
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": f"{hit_rate:.2%}",
            "memory_usage_mb": self._estimate_memory_usage() / 1024 / 1024
        }
```

### 9.2 批量评估优化
```python
# core/opa_policy/batch_evaluator.py
import asyncio
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

class BatchEvaluator:
    """批量评估器"""
    
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.batch_size = 100
        
    async def evaluate_batch(self, policy_code: str, inputs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量评估策略"""
        results = []
        
        # 分批次处理
        for i in range(0, len(inputs), self.batch_size):
            batch = inputs[i:i + self.batch_size]
            batch_results = await self._evaluate_batch_async(policy_code, batch)
            results.extend(batch_results)
            
        return results
    
    async def _evaluate_batch_async(self, policy_code: str, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """异步批量评估"""
        loop = asyncio.get_event_loop()
        tasks = []
        
        for input_data in batch:
            task = loop.run_in_executor(
                self.executor,
                self._evaluate_sync,
                policy_code,
                input_data
            )
            tasks.append(task)
            
        return await asyncio.gather(*tasks)
    
    def _evaluate_sync(self, policy_code: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """同步评估（在子线程中执行）"""
        import rego
        module = rego.parse(policy_code)
        result = module.evaluate(input_data)
        return result
```

## 10. 监控与审计

### 10.1 策略执行监控
```python
# core/opa_policy/monitor.py
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import defaultdict

class PolicyMonitor:
    """策略执行监控器"""
    
    def __init__(self, retention_days: int = 30):
        self.execution_logs = []
        self.retention_days = retention_days
        self.statistics = defaultdict(int)
        
    def log_execution(self, policy: str, input_data: Dict[str, Any], 
                     result: Dict[str, Any], execution_time_ms: float):
        """记录执行日志"""
        log_entry = {
            "timestamp": datetime.now(),
            "policy": policy,
            "input_hash": self._hash_input(input_data),
            "result": result,
            "execution_time_ms": execution_time_ms,
            "allowed": result.get("allow", False)
        }
        
        self.execution_logs.append(log_entry)
        self._update_statistics(log_entry)
        self._cleanup_old_logs()
    
    def _update_statistics(self, log_entry: Dict[str, Any]):
        """更新统计信息"""
        policy = log_entry["policy"]
        self.statistics[f"{policy}_total"] += 1
        self.statistics[f"{policy}_allowed"] += 1 if log_entry["allowed"] else 0
        self.statistics[f"{policy}_denied"] += 0 if log_entry["allowed"] else 1
        self.statistics["total_execution_time_ms"] += log_entry["execution_time_ms"]
    
    def get_statistics(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """获取统计信息"""
        cutoff = datetime.now() - timedelta(hours=time_window_hours)
        recent_logs = [log for log in self.execution_logs if log["timestamp"] > cutoff]
        
        return {
            "time_window_hours": time_window_hours,
            "total_executions": len(recent_logs),
            "avg_execution_time_ms": self._calculate_avg_time(recent_logs),
            "allow_rate": self._calculate_allow_rate(recent_logs),
            "top_policies": self._get_top_policies(recent_logs, top_n=5),
            "slowest_executions": self._get_slowest_executions(recent_logs, top_n=10)
        }
```

## 11. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-11 | 初始版本 |
| 1.1.0 | 2026-04-12 | 新增策略调试工具、性能优化、监控审计功能 |

---

**相关文档**:
- [权限校验模块设计](../permission_checker/DESIGN.md)
- [Hook 系统模块设计](../hook_system/DESIGN.md)
- [OpenHarness 桥接模块设计](../openharness_bridge/DESIGN.md)
- [安全策略文档](../../security/SECURITY.md)
