# 权限校验模块设计文档

> **优先级**: P1 | **相关 ADR**: ADR-003, ADR-028

## 1. 模块概述

**版本**: 1.0.0 | **日期**: 2026-04-12 | **作者**: 平台安全组

### 1.1 核心定位

权限校验模块是Graphiti系统的**安全基石**，基于Open Policy Agent (OPA)实现**统一、声明式、细粒度**的访问控制策略。通过集中式策略管理，为所有Agent操作、数据访问、工具调用提供**一致性**的安全保障，满足领域仿真系统的**最高安全要求**。

### 1.2 核心价值

| 维度 | 价值 | 说明 |
|------|------|------|
| **统一安全** | 集中策略管理 | 所有访问控制通过统一策略引擎，避免策略碎片化 |
| **细粒度控制** | 属性级权限 | 支持用户、角色、资源、环境、时间等多维度属性 |
| **实时生效** | 动态策略更新 | 策略变更实时生效，无需重启系统 |
| **声明式策略** | 策略即代码 | 使用Rego语言编写策略，支持版本控制和审计 |
| **高性能** | 本地策略缓存 | 策略编译和缓存，毫秒级决策响应 |
| **可扩展** | 策略即插件 | 支持自定义策略包，灵活应对新安全需求 |

### 1.3 架构位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OpenHarness Agent 基础设施层                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐           │
│  │ Commander Agent │  │Intelligence Agent│  │Operations Agent │           │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘           │
│           │                    │                    │                    │
│           └────────────────────┼────────────────────┘                    │
│                                ▼                                            │
│                    ┌─────────────────────┐                                  │
│                    │  Swarm Coordinator  │                                  │
│                    │    (OpenHarness)    │                                  │
│                    └──────────┬──────────┘                                  │
│                               │                                              │
│         ┌─────────────────────┼─────────────────────┐                       │
│         ▼                     ▼                     ▼                       │
│  ┌─────────────┐      ┌─────────────┐       ┌─────────────┐                │
│  │Tool Registry│      │ Hook System │       │Permission   │                │
│  │  (43+工具)  │      │ (Pre/Post)  │       │  Checker    │                │
│  └─────────────┘      └─────────────┘       └─────────────┘                │
│                               │                                              │
│                               ▼                                              │
│                    ┌─────────────────────┐                                  │
│                    │      OPA引擎        │                                  │
│                    │  (策略治理层)        │                                  │
│                    │  • 策略管理         │                                  │
│                    │  • 策略编译         │                                  │
│                    │  • 决策执行         │                                  │
│                    │  • 审计日志         │                                  │
│                    └─────────────────────┘                                  │
│                               │                                              │
│         ┌─────────────────────┼─────────────────────┐                       │
│         ▼                     ▼                     ▼                       │
│  ┌─────────────┐      ┌─────────────┐       ┌─────────────┐                │
│  │ 策略库      │      │  策略缓存    │       │ 审计存储    │                │
│  │ (Policy     │      │  (Policy    │       │ (Audit      │                │
│  │   Store)    │      │   Cache)    │       │   Storage)  │                │
│  └─────────────┘      └─────────────┘       └─────────────┘                │
```

---

## 2. 架构设计

### 2.1 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           权限校验模块 (Permission Checker)                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                       策略管理服务 (Policy Manager)                            │    │
│  │  • 策略加载/卸载                                                              │    │
│  │  • 策略版本控制                                                               │    │
│  │  • 策略依赖解析                                                               │    │
│  │  • 策略元数据管理                                                             │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                                │
│         ┌────────────────────────────┼────────────────────────────┐                  │
│         ▼                            ▼                            ▼                  │
│  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐              │
│  │   OPA客户端  │          │  策略编译器  │          │  决策引擎    │              │
│  │ (OPA         │          │ (Policy      │          │ (Decision    │              │
│  │   Client)    │          │   Compiler)  │           │  Engine)    │              │
│  │  • REST API  │          │  • Rego解析  │           │ • 规则匹配  │              │
│  │  • WebSocket │          │  • AST构建  │           │ • 查询执行  │              │
│  │  • 批量查询  │          │  • 字节码生成│           │ • 结果聚合  │              │
│  └──────────────┘          └──────────────┘           └──────────────┘              │
│                                      │                                                │
│         ┌────────────────────────────┼────────────────────────────┐                  │
│         ▼                            ▼                            ▼                  │
│  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐              │
│  │  策略缓存    │          │  审计服务    │          │  监控服务    │              │
│  │ (Policy      │          │ (Audit       │          │ (Monitoring  │              │
│  │   Cache)     │          │   Service)   │          │   Service)   │              │
│  │  • LRU缓存   │          │  • 操作日志  │          │ • 性能指标   │              │
│  │  • 过期策略  │          │  • 安全事件  │          │ • 健康检查   │              │
│  │  • 预加载    │          │  • 合规报告  │          │ • 告警规则   │              │
│  └──────────────┘          └──────────────┘           └──────────────┘              │
│                                      │                                                │
│                                      ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                        策略存储层 (Policy Storage)                             │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐│    │
│  │  │  Git仓库   │ │ 数据库     │ │  文件系统   │ │ 云存储    │ │ API网关   ││    │
│  │  │  (Policy   │ │ (Database) │ │  (File      │ │ (Cloud     │ │ (API       ││    │
│  │  │   Repo)    │ │            │ │  System)    │ │  Storage)  │ │  Gateway)  ││    │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └────────────┘│    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 策略管理服务 (PolicyManager)
- **职责**: 管理所有策略的生命周期，提供策略的加载、卸载、版本控制
- **功能**:
  - 策略的动态加载和卸载
  - 策略版本管理和回滚
  - 策略依赖解析和冲突检测
  - 策略元数据管理和查询

#### 2.2.2 OPA客户端 (OPAClient)
- **职责**: 与OPA引擎通信，执行策略查询和决策
- **功能**:
  - REST API请求封装
  - WebSocket实时连接
  - 批量决策执行
  - 错误处理和重试

#### 2.2.3 策略编译器 (PolicyCompiler)
- **职责**: 编译和优化策略，生成可执行的字节码
- **功能**:
  - Rego语法解析和验证
  - 抽象语法树(AST)构建
  - 优化规则重写
  - 字节码生成和缓存

#### 2.2.4 决策引擎 (DecisionEngine)
- **职责**: 执行策略决策，提供访问控制判断
- **功能**:
  - 规则匹配和查询执行
  - 多策略结果聚合
  - 决策缓存和失效
  - 性能监控和调优

### 2.3 权限决策流程

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   权限请求阶段   │    │  策略评估阶段   │    │  决策响应阶段   │
│                 │    │                 │    │                 │
│ 1. 接收请求     │───▶│ 4. 加载策略     │───▶│ 7. 生成决策     │
│    • 用户身份   │    │    • 策略库     │    │    • 允许/拒绝  │
│    • 操作类型   │    │    • 策略缓存   │    │    • 附加条件   │
│    • 资源信息   │    │                 │    │                 │
│                 │    │ 5. 策略编译     │    │ 8. 记录审计     │
│ 2. 构建输入     │    │    • 语法解析  │    │    • 操作日志   │
│    • 用户属性   │    │    • 优化重写  │    │    • 安全事件   │
│    • 资源属性   │    │    • 字节码生成│    │                 │
│    • 环境属性   │    │                 │    │ 9. 返回结果     │
│                 │    │ 6. 规则匹配     │    │    • 决策结果   │
│ 3. 请求预处理   │───▶│    • 查询执行  │───▶│    • 原因说明   │
│    • 参数校验   │    │    • 结果聚合  │    │    • 建议操作   │
│    • 格式转换   │    │                 │    │                 │
│    • 上下文构建 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 2.4 权限模型

#### 2.4.1 访问控制模型层次
```python
class AccessControlModel(Enum):
    """访问控制模型"""
    RBAC = "rbac"          # 基于角色的访问控制
    ABAC = "abac"          # 基于属性的访问控制
    PBAC = "pbac"          # 基于策略的访问控制
    CBAC = "cbac"          # 基于上下文的访问控制
    
class PermissionScope(Enum):
    """权限作用域"""
    SYSTEM = "system"      # 系统级权限
    PROJECT = "project"    # 项目级权限
    RESOURCE = "resource"  # 资源级权限
    DATA = "data"          # 数据级权限
```

#### 2.4.2 权限决策矩阵
```
┌─────────────────────────────────────────────────────────────────────────┐
│                        权限决策矩阵 (Permission Matrix)                   │
├─────────────────┬─────────────────┬─────────────────┬───────────────────┤
│     权限等级      │   操作类型      │   资源类型       │   决策策略         │
├─────────────────┼─────────────────┼─────────────────┼───────────────────┤
│   SYSTEM_ADMIN  │ 所有操作        │ 所有资源        │ 无条件允许        │
├─────────────────┼─────────────────┼─────────────────┼───────────────────┤
│   PROJECT_OWNER │ read/write      │ 所属项目资源     │ 基于项目成员关系  │
├─────────────────┼─────────────────┼─────────────────┼───────────────────┤
│   TEAM_LEADER   │ read/update     │ 团队资源         │ 基于团队角色      │
├─────────────────┼─────────────────┼─────────────────┼───────────────────┤
│   MEMBER        │ read            │ 可访问资源       │ 基于RBAC+ABAC    │
├─────────────────┼─────────────────┼─────────────────┼───────────────────┤
│   GUEST         │ limited_read    │ 公开资源         │ 基于时间/IP限制  │
└─────────────────┴─────────────────┴─────────────────┴───────────────────┘
```

---

## 3. 技术实现

### 3.1 核心接口设计

#### 3.1.1 OPA客户端接口
```python
# core/permission/opa_client.py
from typing import Dict, List, Any, Optional
import aiohttp
import json
from datetime import datetime
from enum import Enum
import asyncio

class OPAOperation(Enum):
    """OPA操作类型"""
    POLICY_DECISION = "policy_decision"      # 策略决策
    POLICY_LOAD = "policy_load"              # 策略加载
    POLICY_QUERY = "policy_query"            # 策略查询
    HEALTH_CHECK = "health_check"            # 健康检查

class OPAClient:
    """OPA客户端"""
    
    def __init__(self, opa_endpoint: str, timeout: int = 10):
        self.opa_endpoint = opa_endpoint.rstrip('/')
        self.timeout = timeout
        self.session = None
        
    async def connect(self):
        """建立连接"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
    async def close(self):
        """关闭连接"""
        if self.session:
            await self.session.close()
            self.session = None
            
    async def check_permission(self,
                              policy_name: str,
                              input_data: Dict[str, Any],
                              user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """检查权限"""
        url = f"{self.opa_endpoint}/v1/data/{policy_name}"
        
        request_body = {
            "input": input_data
        }
        
        if user_context:
            request_body["context"] = user_context
            
        try:
            async with self.session.post(
                url,
                json=request_body,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return self._parse_decision_result(result)
                else:
                    return {
                        "allow": False,
                        "reason": f"OPA request failed with status {response.status}",
                        "details": await response.text()
                    }
                    
        except asyncio.TimeoutError:
            return {
                "allow": False,
                "reason": f"OPA request timeout after {self.timeout}s"
            }
        except Exception as e:
            return {
                "allow": False,
                "reason": f"OPA request error: {str(e)}"
            }
            
    async def load_policy(self,
                         policy_name: str,
                         policy_content: str) -> Dict[str, Any]:
        """加载策略"""
        url = f"{self.opa_endpoint}/v1/policies/{policy_name}"
        
        try:
            async with self.session.put(
                url,
                data=policy_content,
                headers={"Content-Type": "text/plain"}
            ) as response:
                if response.status == 200:
                    return {
                        "success": True,
                        "message": f"Policy {policy_name} loaded successfully"
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Failed to load policy: {await response.text()}"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "message": f"Error loading policy: {str(e)}"
            }
            
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        url = f"{self.opa_endpoint}/health"
        
        try:
            async with self.session.get(url) as response:
                return {
                    "healthy": response.status == 200,
                    "status": response.status,
                    "response_time_ms": None  # 需要实际测量
                }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
            
    def _parse_decision_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """解析决策结果"""
        if "result" not in result:
            return {
                "allow": False,
                "reason": "No decision result found"
            }
            
        decision_data = result["result"]
        
        # 解析标准OPA决策格式
        if isinstance(decision_data, dict):
            return {
                "allow": decision_data.get("allow", False),
                "reason": decision_data.get("reason", "Decision made"),
                "conditions": decision_data.get("conditions", []),
                "constraints": decision_data.get("constraints", {}),
                "metadata": decision_data.get("metadata", {})
            }
        elif isinstance(decision_data, bool):
            return {
                "allow": decision_data,
                "reason": "Boolean decision"
            }
        else:
            return {
                "allow": False,
                "reason": f"Unexpected decision format: {type(decision_data)}"
            }
```

#### 3.1.2 权限决策服务接口
```python
# core/permission/decision_service.py
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
import hashlib
import json

class DecisionResult(Enum):
    """决策结果"""
    ALLOW = "allow"
    DENY = "deny"
    CONDITIONAL = "conditional"

class DecisionReason(Enum):
    """决策原因"""
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    INSUFFICIENT_ROLE = "insufficient_role"
    RESOURCE_RESTRICTED = "resource_restricted"
    TIME_RESTRICTION = "time_restriction"
    IP_RESTRICTION = "ip_restriction"

@dataclass
class PermissionRequest:
    """权限请求"""
    user_id: str
    user_roles: List[str]
    user_attributes: Dict[str, Any]
    action: str
    resource_type: str
    resource_id: str
    resource_attributes: Dict[str, Any]
    environment: Dict[str, Any]
    request_id: str
    timestamp: datetime

@dataclass
class PermissionDecision:
    """权限决策"""
    request: PermissionRequest
    result: DecisionResult
    reason: DecisionReason
    constraints: Dict[str, Any]
    decision_time: datetime
    decision_id: str
    policy_version: str

class PermissionDecisionService:
    """权限决策服务"""
    
    def __init__(self, opa_client: OPAClient):
        self.opa_client = opa_client
        self.decision_cache: Dict[str, PermissionDecision] = {}
        self.stats = DecisionStatistics()
        
    async def check_permission(self,
                              request: PermissionRequest) -> PermissionDecision:
        """检查权限并返回决策"""
        # 检查缓存
        cache_key = self._generate_cache_key(request)
        if cache_key in self.decision_cache:
            cached_decision = self.decision_cache[cache_key]
            if not self._is_decision_expired(cached_decision):
                self.stats.cache_hits += 1
                return cached_decision
            else:
                del self.decision_cache[cache_key]
                
        self.stats.cache_misses += 1
        
        # 构建OPA输入
        input_data = self._build_opa_input(request)
        
        # 调用OPA进行决策
        start_time = datetime.utcnow()
        opa_result = await self.opa_client.check_permission(
            policy_name=self._get_policy_name(request.resource_type),
            input_data=input_data
        )
        decision_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # 解析决策结果
        decision = self._parse_opa_result(opa_result, request)
        decision.decision_time = start_time
        
        # 更新统计
        self.stats.total_requests += 1
        self.stats.avg_decision_time_ms = (
            (self.stats.avg_decision_time_ms * (self.stats.total_requests - 1) + decision_time)
            / self.stats.total_requests
        )
        
        # 缓存决策（如果允许缓存）
        if self._should_cache_decision(decision):
            self.decision_cache[cache_key] = decision
            
        return decision
        
    def _build_opa_input(self, request: PermissionRequest) -> Dict[str, Any]:
        """构建OPA输入数据"""
        return {
            "user": {
                "id": request.user_id,
                "roles": request.user_roles,
                "attributes": request.user_attributes
            },
            "action": request.action,
            "resource": {
                "type": request.resource_type,
                "id": request.resource_id,
                "attributes": request.resource_attributes
            },
            "environment": request.environment,
            "context": {
                "request_id": request.request_id,
                "timestamp": request.timestamp.isoformat()
            }
        }
        
    def _parse_opa_result(self,
                         opa_result: Dict[str, Any],
                         request: PermissionRequest) -> PermissionDecision:
        """解析OPA结果"""
        if opa_result.get("allow"):
            result = DecisionResult.ALLOW
            reason = DecisionReason.PERMISSION_GRANTED
        else:
            result = DecisionResult.DENY
            reason = DecisionReason.PERMISSION_DENIED
            
        return PermissionDecision(
            request=request,
            result=result,
            reason=reason,
            constraints=opa_result.get("constraints", {}),
            decision_time=datetime.utcnow(),
            decision_id=self._generate_decision_id(),
            policy_version=opa_result.get("metadata", {}).get("version", "unknown")
        )
        
    def _generate_cache_key(self, request: PermissionRequest) -> str:
        """生成缓存键"""
        key_data = {
            "user_id": request.user_id,
            "action": request.action,
            "resource_type": request.resource_type,
            "resource_id": request.resource_id,
            "environment_hash": hashlib.md5(
                json.dumps(request.environment, sort_keys=True).encode()
            ).hexdigest()
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return f"perm_decision:{hashlib.md5(key_str.encode()).hexdigest()}"
        
    def _is_decision_expired(self, decision: PermissionDecision) -> bool:
        """检查决策是否过期"""
        max_age_seconds = 60  # 决策最大有效期
        age = (datetime.utcnow() - decision.decision_time).total_seconds()
        return age > max_age_seconds
        
    def _should_cache_decision(self, decision: PermissionDecision) -> bool:
        """判断是否应该缓存决策"""
        # 只缓存允许的决策，且没有复杂的约束条件
        if decision.result == DecisionResult.ALLOW:
            return len(decision.constraints) == 0
        return False
        
    def _generate_decision_id(self) -> str:
        """生成决策ID"""
        import uuid
        return str(uuid.uuid4())
        
    def _get_policy_name(self, resource_type: str) -> str:
        """根据资源类型获取策略名称"""
        return f"graphiti/{resource_type}_policy"
```

### 3.2 策略设计

#### 3.2.1 核心策略架构
```
┌─────────────────────────────────────────────────────────────────────────┐
│                              策略架构 (Policy Architecture)                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   策略包 (Policy Bundle)                         │   │
│  │  • 基础策略包 (base.rego)                                        │   │
│  │  • 角色定义包 (roles.rego)                                       │   │
│  │  • 资源策略包 (resource_policies.rego)                           │   │
│  │  • 环境策略包 (environment_policies.rego)                        │   │
│  │  • 时间策略包 (time_policies.rego)                               │   │
│  │  • 自定义策略包 (custom_policies.rego)                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│         ┌─────────────────────────────────────────────────────────┐     │
│         │                    策略层次 (Policy Layers)                │     │
│         ├─────────────────────────────────────────────────────────┤     │
│         │  系统级策略 (System-Level)                               │     │
│         │  • 超级管理员权限                                        │     │
│         │  • 系统配置访问                                          │     │
│         │  • 审计日志查看                                          │     │
│         ├─────────────────────────────────────────────────────────┤     │
│         │  项目级策略 (Project-Level)                              │     │
│         │  • 项目成员管理                                          │     │
│         │  • 项目资源访问                                          │     │
│         │  • 项目配置修改                                          │     │
│         ├─────────────────────────────────────────────────────────┤     │
│         │  资源级策略 (Resource-Level)                             │     │
│         │  • 工具调用权限                                          │     │
│         │  • 数据读写控制                                          │   │
│         │  • 文件操作限制                                          │   │
│         └─────────────────────────────────────────────────────────┘   │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 3.2.2 基础策略包示例
```rego
# policies/base.rego
package graphiti.base

# 默认拒绝所有请求
default allow = false

# 定义系统角色
system_roles := {
    "system_admin": {
        "description": "系统管理员",
        "permissions": ["*"]
    },
    "auditor": {
        "description": "审计员",
        "permissions": ["read", "audit"]
    },
    "operator": {
        "description": "操作员",
        "permissions": ["read", "execute"]
    }
}

# 允许条件：用户具有系统管理员角色
allow {
    user_is_system_admin
}

user_is_system_admin {
    input.user.roles[_] == "system_admin"
}

# 允许条件：用户具有审计员角色，且操作为读取或审计
allow {
    user_is_auditor
    action_is_read_or_audit
}

user_is_auditor {
    input.user.roles[_] == "auditor"
}

action_is_read_or_audit {
    input.action == "read"
}

action_is_read_or_audit {
    input.action == "audit"
}
```

#### 3.2.3 工具调用策略包示例
```rego
# policies/tools_policy.rego
package graphiti.tools

import data.graphiti.base
import data.graphiti.roles

# 工具调用权限检查
allow {
    # 调用基础包的权限检查
    base.allow
    
    # 检查用户是否有工具调用权限
    user_has_tool_permission
}

# 用户是否有工具调用权限
user_has_tool_permission {
    # 获取用户角色
    user_role := roles.get_user_role(input.user.id)
    
    # 获取工具权限要求
    tool_perm_required := get_tool_permission_required(input.resource.id)
    
    # 检查角色是否包含所需权限
    roles.role_has_permission(user_role, tool_perm_required)
}

# 工具权限要求映射
get_tool_permission_required(tool_id) = perm {
    tool_permissions[tool_id]
    perm := tool_permissions[tool_id]
}

# 工具权限定义
tool_permissions := {
    "domain.get_scenario": "read",
    "domain.simulate_attack": "execute",
    "radar.get_detections": "read",
    "weather.get_current": "read"
}
```

#### 3.2.4 基于属性的访问控制策略
```rego
# policies/abac_policy.rego
package graphiti.abac

# 基于属性的访问控制策略
allow {
    # 用户属性检查
    user_attribute_check
    
    # 资源属性检查
    resource_attribute_check
    
    # 环境属性检查
    environment_attribute_check
    
    # 时间限制检查
    time_restriction_check
}

# 用户属性检查
user_attribute_check {
    # 用户必须已认证
    input.user.attributes.authenticated == true
    
    # 用户安全等级必须足够
    input.user.attributes.security_level >= required_security_level
}

# 资源属性检查
resource_attribute_check {
    # 资源必须处于可用状态
    input.resource.attributes.status == "available"
    
    # 资源机密等级必须匹配用户权限
    input.resource.attributes.confidentiality_level <= user_max_confidentiality_level
}

# 环境属性检查
environment_attribute_check {
    # 请求必须来自内部网络
    input.environment.network_type == "internal"
    
    # 请求时间必须在工作时间
    input.environment.time_of_day >= "09:00"
    input.environment.time_of_day <= "18:00"
}

# 时间限制检查
time_restriction_check {
    # 检查请求时间是否在允许的时间范围内
    time.clock(input.environment.current_time, "UTC")
    time.hour >= 9
    time.hour <= 18
}

# 计算所需安全等级
required_security_level := 3

# 计算用户最大机密等级
user_max_confidentiality_level := 2 {
    input.user.attributes.security_level >= 4
}

user_max_confidentiality_level := 1 {
    input.user.attributes.security_level >= 2
    input.user.attributes.security_level < 4
}
```

### 3.3 策略缓存与优化

#### 3.3.1 策略缓存管理器
```python
# core/permission/policy_cache.py
from typing import Dict, Any, Optional
import asyncio
from datetime import datetime, timedelta
import hashlib
import json
from dataclasses import dataclass
from enum import Enum

class CacheStrategy(Enum):
    """缓存策略"""
    LRU = "lru"           # 最近最少使用
    LFU = "lfu"           # 最不经常使用
    ARC = "arc"           # 自适应替换缓存
    TTL = "ttl"           # 生存时间

@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    expires_at: Optional[datetime] = None

class PolicyCacheManager:
    """策略缓存管理器"""
    
    def __init__(self, 
                 max_size: int = 1000,
                 strategy: CacheStrategy = CacheStrategy.LRU,
                 default_ttl: int = 300):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.strategy = strategy
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0
        
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key not in self.cache:
            self.misses += 1
            return None
            
        entry = self.cache[key]
        
        # 检查是否过期
        if entry.expires_at and datetime.utcnow() > entry.expires_at:
            await self.evict(key)
            self.misses += 1
            return None
            
        # 更新访问信息
        entry.last_accessed = datetime.utcnow()
        entry.access_count += 1
        
        self.hits += 1
        
        # 根据策略调整缓存位置
        if self.strategy == CacheStrategy.LRU:
            await self._adjust_lru_order(entry)
            
        return entry.value
        
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存值"""
        if len(self.cache) >= self.max_size:
            await self._evict_according_to_strategy()
            
        expires_at = None
        if ttl:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        elif self.default_ttl:
            expires_at = datetime.utcnow() + timedelta(seconds=self.default_ttl)
            
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            access_count=1,
            expires_at=expires_at
        )
        
        self.cache[key] = entry
        
    async def evict(self, key: str):
        """移除缓存条目"""
        if key in self.cache:
            del self.cache[key]
            
    async def clear(self):
        """清空缓存"""
        self.cache.clear()
        
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total": total,
            "hit_rate_percent": hit_rate,
            "cache_size": len(self.cache),
            "max_size": self.max_size,
            "strategy": self.strategy.value
        }
        
    async def _adjust_lru_order(self, entry: CacheEntry):
        """调整LRU顺序"""
        # 在实际实现中，可能需要重新排序缓存
        pass
        
    async def _evict_according_to_strategy(self):
        """根据策略淘汰缓存"""
        if self.strategy == CacheStrategy.LRU:
            await self._evict_lru()
        elif self.strategy == CacheStrategy.LFU:
            await self._evict_lfu()
        elif self.strategy == CacheStrategy.TTL:
            await self._evict_expired()
            
    async def _evict_lru(self):
        """淘汰最近最少使用的条目"""
        if not self.cache:
            return
            
        # 找到最近最少访问的条目
        lru_entry = min(self.cache.values(), key=lambda e: e.last_accessed)
        await self.evict(lru_entry.key)
        
    async def _evict_lfu(self):
        """淘汰最不经常使用的条目"""
        if not self.cache:
            return
            
        # 找到访问次数最少的条目
        lfu_entry = min(self.cache.values(), key=lambda e: e.access_count)
        await self.evict(lfu_entry.key)
        
    async def _evict_expired(self):
        """淘汰过期条目"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self.cache.items()
            if entry.expires_at and entry.expires_at < now
        ]
        
        for key in expired_keys:
            await self.evict(key)
```

---

## 4. 安全设计

### 4.1 策略安全机制

#### 4.1.1 策略签名验证
```python
# core/permission/security/policy_validator.py
import hashlib
import json
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
import base64

class PolicySignatureValidator:
    """策略签名验证器"""
    
    def __init__(self, public_key_path: str):
        self.public_key = self._load_public_key(public_key_path)
        
    def validate_policy(self, 
                       policy_content: str, 
                       signature: str) -> bool:
        """验证策略签名"""
        try:
            # 计算策略内容的哈希
            policy_hash = hashlib.sha256(policy_content.encode()).hexdigest()
            
            # 解码签名
            signature_bytes = base64.b64decode(signature)
            
            # 验证签名
            self.public_key.verify(
                signature_bytes,
                policy_hash.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except InvalidSignature:
            print("策略签名验证失败：无效签名")
            return False
        except Exception as e:
            print(f"策略签名验证错误：{e}")
            return False
            
    def _load_public_key(self, path: str) -> rsa.RSAPublicKey:
        """加载公钥"""
        with open(path, "rb") as key_file:
            public_key = serialization.load_pem_public_key(
                key_file.read()
            )
        return public_key
        
    def generate_policy_hash(self, policy_content: str) -> str:
        """生成策略哈希"""
        return hashlib.sha256(policy_content.encode()).hexdigest()
```

#### 4.1.2 策略沙箱执行环境
```python
# core/permission/security/policy_sandbox.py
import asyncio
from typing import Dict, Any, Callable
import re

class PolicySandbox:
    """策略沙箱执行环境"""
    
    def __init__(self):
        # 允许的函数和操作
        self.allowed_functions = {
            "math.abs", "math.ceil", "math.floor", "math.round",
            "string.lower", "string.upper", "string.split", "string.trim",
            "array.concat", "array.slice", "array.includes",
            "object.get", "object.keys", "object.values"
        }
        
        # 禁止的操作模式
        self.forbidden_patterns = [
            r"import\s+",          # 禁止导入
            r"exec\(",             # 禁止exec
            r"eval\(",             # 禁止eval
            r"__import__",         # 禁止__import__
            r"open\(",             # 禁止文件操作
            r"os\.",               # 禁止os模块
            r"sys\.",              # 禁止sys模块
            r"subprocess\.",       # 禁止子进程
        ]
        
    async def evaluate_policy(self,
                             policy_function: Callable,
                             input_data: Dict[str, Any]) -> Dict[str, Any]:
        """在沙箱中评估策略函数"""
        try:
            # 验证策略函数
            self._validate_policy_function(policy_function)
            
            # 执行策略函数
            result = await policy_function(input_data)
            
            return {
                "success": True,
                "result": result,
                "sanitized": True
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "sanitized": True
            }
            
    def _validate_policy_function(self, func: Callable):
        """验证策略函数的安全性"""
        # 检查函数代码
        func_code = func.__code__
        
        # 检查禁止的操作模式
        func_source = self._get_function_source(func)
        for pattern in self.forbidden_patterns:
            if re.search(pattern, func_source, re.IGNORECASE):
                raise SecurityError(f"Forbidden pattern detected: {pattern}")
                
        # 检查允许的函数调用
        # 在实际实现中，可能需要更复杂的AST分析
        
    def _get_function_source(self, func: Callable) -> str:
        """获取函数源代码"""
        import inspect
        try:
            source = inspect.getsource(func)
            return source
        except:
            return ""
            
class SecurityError(Exception):
    """安全错误"""
    pass
```

### 4.2 访问控制审计

#### 4.2.1 审计日志记录器
```python
# core/permission/audit/audit_logger.py
from typing import Dict, Any, Optional
from datetime import datetime
import json
from enum import Enum
from dataclasses import dataclass
import hashlib

class AuditEventType(Enum):
    """审计事件类型"""
    PERMISSION_CHECK = "permission_check"
    POLICY_LOAD = "policy_load"
    POLICY_MODIFY = "policy_modify"
    SECURITY_EVENT = "security_event"
    CONFIG_CHANGE = "config_change"

class AuditSeverity(Enum):
    """审计严重级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class AuditRecord:
    """审计记录"""
    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    user_id: Optional[str]
    action: str
    resource_type: str
    resource_id: str
    decision: str
    reason: str
    severity: AuditSeverity
    ip_address: Optional[str]
    user_agent: Optional[str]
    metadata: Dict[str, Any]
    signature: Optional[str] = None

class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, storage_backend: str = "elasticsearch"):
        self.storage_backend = storage_backend
        
    async def log_permission_check(self,
                                  request: Dict[str, Any],
                                  decision: Dict[str, Any],
                                  user_context: Optional[Dict[str, Any]] = None) -> str:
        """记录权限检查审计日志"""
        audit_record = AuditRecord(
            event_id=self._generate_event_id(),
            event_type=AuditEventType.PERMISSION_CHECK,
            timestamp=datetime.utcnow(),
            user_id=request.get("user_id"),
            action=request.get("action"),
            resource_type=request.get("resource_type"),
            resource_id=request.get("resource_id"),
            decision=decision.get("result", "unknown"),
            reason=decision.get("reason", "no reason"),
            severity=self._determine_severity(decision),
            ip_address=user_context.get("ip_address") if user_context else None,
            user_agent=user_context.get("user_agent") if user_context else None,
            metadata={
                "request": request,
                "decision": decision,
                "context": user_context or {}
            }
        )
        
        # 对记录进行签名（可选）
        if self._should_sign_audit_record():
            audit_record.signature = self._sign_audit_record(audit_record)
            
        # 存储审计记录
        await self._store_audit_record(audit_record)
        
        return audit_record.event_id
        
    async def log_security_event(self,
                                event_type: str,
                                description: str,
                                severity: AuditSeverity,
                                user_id: Optional[str] = None,
                                metadata: Optional[Dict[str, Any]] = None) -> str:
        """记录安全事件审计日志"""
        audit_record = AuditRecord(
            event_id=self._generate_event_id(),
            event_type=AuditEventType.SECURITY_EVENT,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            action=event_type,
            resource_type="security",
            resource_id="event",
            decision="logged",
            reason=description,
            severity=severity,
            ip_address=None,
            user_agent=None,
            metadata=metadata or {}
        )
        
        await self._store_audit_record(audit_record)
        
        return audit_record.event_id
        
    def _generate_event_id(self) -> str:
        """生成事件ID"""
        import uuid
        return str(uuid.uuid4())
        
    def _determine_severity(self, decision: Dict[str, Any]) -> AuditSeverity:
        """确定审计严重级别"""
        if not decision.get("allow", False):
            return AuditSeverity.HIGH
        else:
            return AuditSeverity.LOW
            
    def _should_sign_audit_record(self) -> bool:
        """判断是否需要签名审计记录"""
        return True  # 在生产环境中应该启用
        
    def _sign_audit_record(self, record: AuditRecord) -> str:
        """对审计记录进行签名"""
        # 在实际实现中，需要使用私钥进行签名
        record_str = json.dumps(self._record_to_dict(record), sort_keys=True)
        return hashlib.sha256(record_str.encode()).hexdigest()
        
    def _record_to_dict(self, record: AuditRecord) -> Dict[str, Any]:
        """将审计记录转换为字典"""
        return {
            "event_id": record.event_id,
            "event_type": record.event_type.value,
            "timestamp": record.timestamp.isoformat(),
            "user_id": record.user_id,
            "action": record.action,
            "resource_type": record.resource_type,
            "resource_id": record.resource_id,
            "decision": record.decision,
            "reason": record.reason,
            "severity": record.severity.value,
            "ip_address": record.ip_address,
            "user_agent": record.user_agent,
            "metadata": record.metadata
        }
        
    async def _store_audit_record(self, record: AuditRecord):
        """存储审计记录"""
        if self.storage_backend == "elasticsearch":
            await self._store_to_elasticsearch(record)
        elif self.storage_backend == "database":
            await self._store_to_database(record)
        else:
            # 默认存储到文件
            await self._store_to_file(record)
```

---

## 5. 监控与运维

### 5.1 监控指标

#### 5.1.1 权限检查性能指标
```python
# core/permission/monitoring/permission_metrics.py
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class PermissionMetricType(Enum):
    """权限指标类型"""
    CHECK_COUNT = "check_count"
    CHECK_DURATION = "check_duration"
    ALLOW_RATE = "allow_rate"
    DENY_RATE = "deny_rate"
    CACHE_HIT_RATE = "cache_hit_rate"
    POLICY_LOAD_COUNT = "policy_load_count"

@dataclass
class PermissionMetric:
    """权限监控指标"""
    metric_type: PermissionMetricType
    value: float
    labels: Dict[str, str]
    timestamp: datetime

class PermissionMetricsCollector:
    """权限指标收集器"""
    
    def __init__(self):
        self.metrics: Dict[str, List[PermissionMetric]] = {}
        
    def record_permission_check(self,
                               resource_type: str,
                               action: str,
                               decision_result: str,
                               duration_ms: float):
        """记录权限检查指标"""
        # 记录检查次数
        self._record_counter(
            metric_type=PermissionMetricType.CHECK_COUNT,
            labels={
                "resource_type": resource_type,
                "action": action,
                "decision": decision_result
            },
            value=1
        )
        
        # 记录检查时长
        self._record_histogram(
            metric_type=PermissionMetricType.CHECK_DURATION,
            labels={
                "resource_type": resource_type,
                "action": action
            },
            value=duration_ms
        )
        
        # 记录允许/拒绝率
        if decision_result == "allow":
            self._record_counter(
                metric_type=PermissionMetricType.ALLOW_RATE,
                labels={"resource_type": resource_type},
                value=1
            )
        else:
            self._record_counter(
                metric_type=PermissionMetricType.DENY_RATE,
                labels={"resource_type": resource_type},
                value=1
            )
            
    def record_cache_hit(self, hit: bool):
        """记录缓存命中率"""
        metric_type = PermissionMetricType.CACHE_HIT_RATE
        label_value = "hit" if hit else "miss"
        
        self._record_counter(
            metric_type=metric_type,
            labels={"result": label_value},
            value=1
        )
        
    def _record_counter(self,
                       metric_type: PermissionMetricType,
                       labels: Dict[str, str],
                       value: float):
        """记录计数器指标"""
        metric = PermissionMetric(
            metric_type=metric_type,
            value=value,
            labels=labels,
            timestamp=datetime.utcnow()
        )
        self._store_metric(metric)
        
    def _record_histogram(self,
                         metric_type: PermissionMetricType,
                         labels: Dict[str, str],
                         value: float):
        """记录直方图指标"""
        metric = PermissionMetric(
            metric_type=metric_type,
            value=value,
            labels=labels,
            timestamp=datetime.utcnow()
        )
        self._store_metric(metric)
        
    def _store_metric(self, metric: PermissionMetric):
        """存储指标"""
        key = metric.metric_type.value
        if key not in self.metrics:
            self.metrics[key] = []
        self.metrics[key].append(metric)
        
        # 限制历史记录数量
        if len(self.metrics[key]) > 1000:
            self.metrics[key] = self.metrics[key][-500:]
            
    def get_summary_stats(self) -> Dict[str, Any]:
        """获取统计摘要"""
        stats = {
            "total_checks": 0,
            "total_allows": 0,
            "total_denies": 0,
            "avg_duration_ms": 0,
            "cache_hit_rate": 0
        }
        
        # 计算统计数据
        for metric_type, metrics in self.metrics.items():
            for metric in metrics:
                if metric_type == "check_count":
                    stats["total_checks"] += metric.value
                elif metric_type == "allow_rate":
                    stats["total_allows"] += metric.value
                elif metric_type == "deny_rate":
                    stats["total_denies"] += metric.value
                    
        # 计算平均持续时间
        duration_metrics = self.metrics.get("check_duration", [])
        if duration_metrics:
            total_duration = sum(m.value for m in duration_metrics)
            stats["avg_duration_ms"] = total_duration / len(duration_metrics)
            
        # 计算缓存命中率
        hit_metrics = self.metrics.get("cache_hit_rate", [])
        if hit_metrics:
            hits = sum(m.value for m in hit_metrics if m.labels.get("result") == "hit")
            total = sum(m.value for m in hit_metrics)
            stats["cache_hit_rate"] = (hits / total * 100) if total > 0 else 0
            
        return stats
```

### 5.2 告警规则

#### 5.2.1 权限安全告警配置
```yaml
# config/permission_alerts.yaml
alerts:
  - name: "permission_high_deny_rate"
    description: "权限拒绝率过高"
    metric: "graphiti_permission_deny_rate"
    condition: "rate_5m > 10"  # 5分钟内拒绝超过10次
    duration: "5m"
    severity: "warning"
    labels:
      component: "permission_checker"
      
  - name: "permission_slow_check"
    description: "权限检查过慢"
    metric: "graphiti_permission_check_duration_seconds"
    condition: "value > 1"    # 检查时间超过1秒
    duration: "2m"
    severity: "warning"
    labels:
      component: "permission_checker"
      
  - name: "permission_policy_load_failed"
    description: "策略加载失败"
    metric: "graphiti_policy_load_errors_total"
    condition: "rate_10m > 5"  # 10分钟内加载失败超过5次
    severity: "critical"
    labels:
      component: "policy_manager"
      
  - name: "permission_audit_log_failure"
    description: "审计日志记录失败"
    metric: "graphiti_audit_log_failures_total"
    condition: "rate_15m > 3"  # 15分钟内失败超过3次
    severity: "high"
    labels:
      component: "audit_logger"
      
  - name: "permission_cache_low_hit_rate"
    description: "权限缓存命中率过低"
    metric: "graphiti_permission_cache_hit_rate"
    condition: "value < 0.7"   # 缓存命中率低于70%
    duration: "10m"
    severity: "medium"
    labels:
      component: "policy_cache"
```

---

## 6. 部署与配置

### 6.1 Docker部署配置

#### 6.1.1 Docker Compose配置
```yaml
# docker-compose.permission.yaml
version: '3.8'

services:
  # OPA策略引擎
  opa:
    image: openpolicyagent/opa:latest
    container_name: opa-policy-engine
    command: ["run", "--server", "--addr", ":8181", "--log-level", "info"]
    ports:
      - "8181:8181"
    volumes:
      - ./policies:/policies
      - ./data/opa:/data
    networks:
      - domain-network
      
  # 权限校验服务
  permission-service:
    build:
      context: .
      dockerfile: docker/permission/Dockerfile
    container_name: permission-service
    ports:
      - "8084:8084"    # 权限API端口
      - "8085:8085"    # 管理API端口
    environment:
      - OPA_ENDPOINT=http://opa:8181
      - PERMISSION_LOG_LEVEL=INFO
      - CACHE_ENABLED=true
      - AUDIT_ENABLED=true
      - SECURITY_VALIDATION_ENABLED=true
    volumes:
      - ./config/permission:/app/config
      - ./logs/permission:/app/logs
      - ./policies:/app/policies
    depends_on:
      - opa
      - redis
      - elasticsearch
    networks:
      - domain-network
      
  # Redis缓存
  redis:
    image: redis:7-alpine
    container_name: permission-redis
    ports:
      - "6380:6379"
    volumes:
      - redis-permission-data:/data
    command: redis-server --appendonly yes
    networks:
      - domain-network
      
  # Elasticsearch审计存储
  elasticsearch:
    image: elasticsearch:8.12.0
    container_name: permission-elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - ES_JAVA_OPTS=-Xms512m -Xmx512m
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch-permission-data:/usr/share/elasticsearch/data
    networks:
      - domain-network

volumes:
  redis-permission-data:
  elasticsearch-permission-data:

networks:
  domain-network:
    driver: bridge
```

### 6.2 配置管理

#### 6.2.1 权限校验配置文件
```yaml
# config/permission_config.yaml
permission:
  # OPA配置
  opa:
    endpoint: "http://opa:8181"
    timeout: 10
    max_retries: 3
    health_check_interval: 30
    
  # 缓存配置
  cache:
    enabled: true
    strategy: "lru"
    max_size: 1000
    default_ttl: 300
    cache_key_prefix: "perm"
    
  # 审计配置
  audit:
    enabled: true
    storage_backend: "elasticsearch"
    elasticsearch_host: "http://elasticsearch:9200"
    index_name: "graphiti-permission-audit"
    retention_days: 365
    enable_signature: true
    
  # 策略配置
  policy:
    base_package: "graphiti.base"
    default_policy_name: "default_policy"
    policy_dir: "/app/policies"
    auto_reload: true
    validation_enabled: true
    
  # 安全配置
  security:
    enable_signature_validation: true
    public_key_path: "/app/config/security/public_key.pem"
    sandbox_enabled: true
    max_policy_size_kb: 1024
    
  # 性能配置
  performance:
    enable_metrics: true
    metrics_port: 8085
    stats_collection_interval: 15
    enable_profiling: false
    
  # 日志配置
  logging:
    level: "INFO"
    format: "json"
    enable_access_log: true
    enable_error_log: true
    log_dir: "/app/logs"
```

---

## 7. API文档

### 7.1 REST API

#### 7.1.1 权限检查API
```
POST   /api/v1/permission/check   # 检查权限
POST   /api/v1/permission/batch   # 批量检查权限
```

#### 7.1.2 策略管理API
```
GET    /api/v1/policies           # 获取所有策略列表
POST   /api/v1/policies          # 创建新策略
GET    /api/v1/policies/{name}   # 获取策略详情
PUT    /api/v1/policies/{name}   # 更新策略
DELETE /api/v1/policies/{name}   # 删除策略
POST   /api/v1/policies/{name}/validate   # 验证策略
```

#### 7.1.3 审计管理API
```
GET    /api/v1/audit/logs        # 查询审计日志
GET    /api/v1/audit/reports     # 生成审计报告
POST   /api/v1/audit/export      # 导出审计数据
```

### 7.2 API使用示例

#### 7.2.1 权限检查请求示例
```json
{
  "user_id": "user-001",
  "user_roles": ["operator", "viewer"],
  "user_attributes": {
    "authenticated": true,
    "security_level": 3,
    "department": "operations"
  },
  "action": "execute",
  "resource_type": "tool",
  "resource_id": "domain.simulate_attack",
  "resource_attributes": {
    "confidentiality_level": 2,
    "status": "available",
    "owner": "system"
  },
  "environment": {
    "network_type": "internal",
    "time_of_day": "14:30",
    "current_time": "2026-04-12T14:30:00Z",
    "client_ip": "192.168.1.100"
  },
  "request_id": "req-20260412-001"
}
```

#### 7.2.2 权限检查响应示例
```json
{
  "success": true,
  "decision": {
    "allow": true,
    "reason": "permission_granted",
    "constraints": {},
    "decision_id": "dec-20260412-001",
    "policy_version": "1.0.0",
    "decision_time": "2026-04-12T14:30:15Z"
  },
  "metadata": {
    "check_duration_ms": 45.2,
    "cache_hit": true,
    "policy_name": "graphiti/tools_policy"
  }
}
```

---

## 8. 版本历史

### 8.1 核心能力总结

1. **统一策略管理**: 基于OPA的声明式策略引擎，提供一致的访问控制
2. **细粒度权限控制**: 支持用户、角色、资源、环境、时间等多维度属性
3. **高性能决策**: 本地策略缓存、智能预编译、毫秒级响应
4. **完整审计追踪**: 全面的审计日志记录、分析和报告
5. **高安全性**: 策略签名验证、沙箱执行、安全配置管理
6. **易于扩展**: 插件化架构，支持自定义策略和集成

### 8.2 应用场景

1. **工具调用权限控制**: 确保只有授权用户才能执行特定工具
2. **数据访问控制**: 实现数据级别的读写权限管理
3. **项目级权限隔离**: 不同项目之间的资源访问隔离
4. **时间/IP限制**: 基于时间和IP地址的访问控制
5. **合规性审计**: 满足安全合规要求的审计记录

### 8.3 性能指标

| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| 权限检查延迟 | < 100ms | 性能测试 |
| 决策吞吐量 | > 1000请求/秒 | 压力测试 |
| 缓存命中率 | > 90% | 监控指标 |
| 系统可用性 | > 99.99% | 运维监控 |
| 策略加载时间 | < 1秒 | 系统测试 |
| 审计日志延迟 | < 50ms | 性能监控 |

---

**文档版本历史**:

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.0.0 | 2026-04-12 | 初始版本，完整设计权限校验模块 |
| v0.1.0 | 2026-04-11 | 草案版本，基础架构设计 |

---

**相关文档**:
- [Open Policy Agent (OPA) 官方文档](https://www.openpolicyagent.org/docs/latest/)
- [Rego策略语言指南](https://www.openpolicyagent.org/docs/latest/policy-language/)
- [Hook系统模块设计](../hook_system/DESIGN.md)
- [MCP协议集成模块设计](../mcp_protocol/DESIGN.md)
- [安全策略文档](../../security/SECURITY.md)