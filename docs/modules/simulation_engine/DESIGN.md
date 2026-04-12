# 模拟推演引擎 (Simulation Engine) - 设计文档

**版本**: 1.0.0 | **日期**: 2026-04-12 | **作者**: Graphiti架构团队

## 🎯 概述

模拟推演引擎是为Graphiti系统设计的**沙箱式推演能力**，支持用户通过Web界面配置参数、模拟不同方案、预演结果，同时保证生产环境的完全隔离。每个推演方案都有独立的版本管理和回退能力。

## 📋 核心特性

### 1. 沙箱隔离机制
- **完全隔离**: 模拟推演在独立的沙箱环境中执行
- **数据隔离**: 使用临时数据库和存储，不影响生产数据
- **环境隔离**: 独立的配置文件、环境变量和依赖项

### 2. 版本化管理
- **方案版本控制**: Git-style的版本管理，支持分支、合并、回退
- **参数快照**: 每次参数调整自动创建快照
- **结果归档**: 推演结果与参数版本关联存储

### 3. Web界面配置
- **实时参数调整**: 通过Web界面动态修改推演参数
- **方案对比**: 并行推演多个方案，对比结果
- **可视化配置**: 拖拽式参数配置界面

### 4. 回滚与恢复
- **任意点回退**: 支持回退到任意历史版本
- **差异对比**: 显示版本间的参数差异
- **一键恢复**: 快速恢复到之前的有效方案

## 🏗️ 架构设计

### 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                模拟推演系统架构 (Simulation Architecture)      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 Web界面层 (UI Layer)                 │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
│  │  │方案管理器│ │参数编辑器│ │结果看板  │            │   │
│  │  │Scenario │ │Parameter │ │Dashboard │            │   │
│  │  │Manager   │ │Editor    │ │          │            │   │
│  │  └─────┬────┘ └────┬────┘ └────┬────┘            │   │
│  └────────┼────────────┼───────────┼─────────────────┘   │
│           │            │           │                     │
│  ┌────────┴────────────┴───────────┴─────────────────┐   │
│  │              API网关层 (API Gateway)                │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐   │   │
│  │  │方案管理API │  │推演执行API │  │版本管理API │   │   │
│  │  │Scenario    │  │Simulation  │  │Version     │   │   │
│  │  │Management  │  │Execution   │  │Management  │   │   │
│  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘   │   │
│  └────────┼───────────────┼────────────────┼─────────┘   │
│           │               │                │             │
│  ┌────────┴───────────────┴────────────────┴─────────┐   │
│  │             核心引擎层 (Core Engine)               │   │
│  │  ┌──────────────────────────────────────────┐    │   │
│  │  │        模拟沙箱 (Simulation Sandbox)      │    │   │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐   │    │   │
│  │  │  │环境隔离 │  │参数注入 │  │结果捕获 │   │    │   │
│  │  │  │Isolated │  │Parameter│  │Result   │   │    │   │
│  │  │  │Environ. │  │Injection│  │Capture  │   │    │   │
│  │  │  └─────────┘  └─────────┘  └─────────┘   │    │   │
│  │  └──────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │             数据存储层 (Data Storage)                │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │方案版本库│  │推演结果库│  │参数快照库│          │   │
│  │  │Scenario  │  │Simulation│  │Parameter │          │   │
│  │  │Versioning│  │Result    │  │Snapshots │          │   │
│  │  │Repo      │  │Store     │  │Store     │          │   │
│  │  └──────────┘  └──────────┘  └──────────┘          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2. 核心组件

#### 2.1 模拟沙箱 (SimulationSandbox)
```python
class SimulationSandbox:
    """
    模拟沙箱 - 提供完全隔离的推演环境
    """
    def __init__(self, scenario_id: str, base_config: Dict):
        self.scenario_id = scenario_id
        self.base_config = base_config
        self.isolation_layer = IsolationLayer()
        self.execution_engine = ExecutionEngine()
        
    async def create_sandbox(self) -> str:
        """创建隔离的沙箱环境"""
        sandbox_id = self.isolation_layer.create_isolated_env()
        
        # 复制基础配置
        await self.isolation_layer.copy_configs(self.base_config)
        
        # 初始化临时存储
        await self.init_temp_storage()
        
        return sandbox_id
    
    async def execute_simulation(
        self, 
        parameters: Dict, 
        scenario_type: str
    ) -> SimulationResult:
        """在沙箱中执行模拟推演"""
        # 注入参数
        injected_params = await self.parameter_injector.inject(parameters)
        
        # 执行推演
        result = await self.execution_engine.execute(
            scenario_type, 
            injected_params
        )
        
        # 捕获结果
        captured_result = await self.result_capturer.capture(result)
        
        return captured_result
    
    async def cleanup(self):
        """清理沙箱环境"""
        await self.isolation_layer.cleanup()
```

#### 2.2 方案版本管理器 (ScenarioVersionManager)
```python
class ScenarioVersionManager:
    """
    方案版本管理 - Git-style版本控制
    """
    def __init__(self, storage_backend: StorageBackend):
        self.storage = storage_backend
        self.version_graph = VersionGraph()
        
    async def create_version(
        self, 
        scenario_config: Dict, 
        parent_version: Optional[str] = None
    ) -> VersionInfo:
        """创建新版本"""
        version_id = generate_version_id()
        
        # 创建版本快照
        snapshot = await self.create_snapshot(scenario_config)
        
        # 添加到版本图
        await self.version_graph.add_version(
            version_id=version_id,
            parent_id=parent_version,
            snapshot=snapshot,
            metadata={
                "created_at": datetime.now(),
                "author": get_current_user(),
                "changes": self.detect_changes(parent_version, scenario_config)
            }
        )
        
        return VersionInfo(
            id=version_id,
            snapshot=snapshot,
            parent=parent_version,
            created_at=datetime.now()
        )
    
    async def get_version(self, version_id: str) -> VersionInfo:
        """获取特定版本"""
        return await self.version_graph.get_version(version_id)
    
    async def list_versions(
        self, 
        scenario_id: str, 
        limit: int = 50
    ) -> List[VersionInfo]:
        """列出所有版本"""
        return await self.version_graph.list_versions(scenario_id, limit)
    
    async def revert_to_version(
        self, 
        scenario_id: str, 
        target_version: str
    ) -> bool:
        """回退到指定版本"""
        # 获取目标版本
        target = await self.get_version(target_version)
        
        # 创建回退版本
        revert_version = await self.create_version(
            target.snapshot.config,
            parent_version=get_current_version(scenario_id)
        )
        
        # 应用回退
        await self.apply_version(revert_version)
        
        return True
```

#### 2.3 参数配置系统 (ParameterConfigSystem)
```python
class ParameterConfigSystem:
    """
    参数配置系统 - 支持Web界面动态配置
    """
    def __init__(self):
        self.parameter_schema = ParameterSchemaRegistry()
        self.validation_rules = ValidationRuleEngine()
        self.ui_generator = UIGenerator()
        
    async def get_parameter_schema(
        self, 
        scenario_type: str
    ) -> Dict:
        """获取参数配置schema"""
        schema = await self.parameter_schema.get_schema(scenario_type)
        
        # 生成UI配置
        ui_config = await self.ui_generator.generate_ui_config(schema)
        
        return {
            "schema": schema,
            "ui_config": ui_config,
            "default_values": self.get_default_values(schema)
        }
    
    async def validate_parameters(
        self, 
        parameters: Dict, 
        schema: Dict
    ) -> ValidationResult:
        """验证参数配置"""
        return await self.validation_rules.validate(parameters, schema)
    
    async def apply_parameters(
        self, 
        scenario_id: str, 
        parameters: Dict,
        create_snapshot: bool = True
    ) -> ApplyResult:
        """应用参数配置"""
        # 验证参数
        validation = await self.validate_parameters(
            parameters, 
            await self.get_parameter_schema(scenario_id)
        )
        
        if not validation.valid:
            return ApplyResult(
                success=False,
                errors=validation.errors
            )
        
        # 应用参数
        applied = await self.apply_to_scenario(scenario_id, parameters)
        
        # 创建参数快照
        if create_snapshot:
            snapshot_id = await self.create_parameter_snapshot(
                scenario_id, 
                parameters
            )
            applied.snapshot_id = snapshot_id
        
        return applied
    
    async def compare_parameters(
        self, 
        version_a: str, 
        version_b: str
    ) -> ParameterDiff:
        """比较两个版本的参数差异"""
        params_a = await self.get_parameters(version_a)
        params_b = await self.get_parameters(version_b)
        
        return self.diff_engine.compare(params_a, params_b)
```

#### 2.4 推演结果分析器 (SimulationResultAnalyzer)
```python
class SimulationResultAnalyzer:
    """
    推演结果分析器 - 分析、对比、可视化结果
    """
    def __init__(self):
        self.metrics_calculator = MetricsCalculator()
        self.comparison_engine = ComparisonEngine()
        self.visualization_generator = VisualizationGenerator()
        
    async def analyze_result(
        self, 
        result: SimulationResult,
        scenario_type: str
    ) -> AnalysisResult:
        """分析推演结果"""
        # 计算关键指标
        metrics = await self.metrics_calculator.calculate(
            result.raw_data,
            scenario_type
        )
        
        # 生成分析报告
        report = await self.generate_analysis_report(metrics)
        
        # 生成可视化
        visualizations = await self.visualization_generator.generate(
            result.raw_data,
            report
        )
        
        return AnalysisResult(
            metrics=metrics,
            report=report,
            visualizations=visualizations,
            recommendations=self.generate_recommendations(metrics)
        )
    
    async def compare_results(
        self, 
        results: List[SimulationResult],
        baseline_id: Optional[str] = None
    ) -> ComparisonResult:
        """对比多个推演结果"""
        # 提取对比维度
        comparison_dimensions = self.extract_comparison_dimensions(results)
        
        # 执行对比分析
        comparison = await self.comparison_engine.compare(
            results,
            comparison_dimensions,
            baseline_id
        )
        
        # 生成对比报告
        comparison_report = await self.generate_comparison_report(comparison)
        
        return ComparisonResult(
            comparison=comparison,
            report=comparison_report,
            winner=self.identify_best_result(comparison),
            insights=self.extract_insights(comparison)
        )
    
    async def generate_what_if_analysis(
        self,
        base_result: SimulationResult,
        parameter_changes: Dict[str, Any]
    ) -> WhatIfResult:
        """生成What-if分析"""
        # 模拟参数变化的影响
        simulated_results = await self.simulate_parameter_changes(
            base_result,
            parameter_changes
        )
        
        # 分析变化趋势
        trend_analysis = await self.analyze_trends(simulated_results)
        
        return WhatIfResult(
            simulated_results=simulated_results,
            trend_analysis=trend_analysis,
            sensitivity_analysis=self.calculate_sensitivity(
                base_result,
                parameter_changes
            ),
            recommendations=self.generate_parameter_recommendations(
                trend_analysis
            )
        )
```

## 🔧 API设计

### 1. 方案管理API

```python
# API端点设计
@router.post("/scenarios")
async def create_scenario(
    request: CreateScenarioRequest
) -> ScenarioResponse:
    """创建新推演方案"""
    pass

@router.get("/scenarios/{scenario_id}")
async def get_scenario(
    scenario_id: str
) -> ScenarioResponse:
    """获取方案详情"""
    pass

@router.put("/scenarios/{scenario_id}/parameters")
async def update_parameters(
    scenario_id: str,
    parameters: Dict[str, Any]
) -> ParameterUpdateResponse:
    """更新方案参数"""
    pass

@router.post("/scenarios/{scenario_id}/simulate")
async def run_simulation(
    scenario_id: str,
    config: Optional[SimulationConfig] = None
) -> SimulationResponse:
    """执行模拟推演"""
    pass
```

### 2. 版本管理API

```python
@router.get("/scenarios/{scenario_id}/versions")
async def list_versions(
    scenario_id: str,
    limit: int = 50,
    offset: int = 0
) -> List[VersionInfo]:
    """列出方案的所有版本"""
    pass

@router.post("/scenarios/{scenario_id}/versions/{version_id}/revert")
async def revert_to_version(
    scenario_id: str,
    version_id: str
) -> RevertResponse:
    """回退到指定版本"""
    pass

@router.get("/scenarios/{scenario_id}/versions/{version_a}/compare/{version_b}")
async def compare_versions(
    scenario_id: str,
    version_a: str,
    version_b: str
) -> VersionComparison:
    """比较两个版本的差异"""
    pass
```

### 3. 推演结果API

```python
@router.get("/simulations/{simulation_id}/results")
async def get_simulation_results(
    simulation_id: str,
    format: str = "json"  # json, csv, html
) -> Union[Dict, str]:
    """获取推演结果"""
    pass

@router.post("/simulations/compare")
async def compare_simulations(
    simulation_ids: List[str],
    comparison_config: ComparisonConfig
) -> ComparisonResult:
    """对比多个推演结果"""
    pass

@router.get("/simulations/{simulation_id}/visualizations")
async def get_visualizations(
    simulation_id: str,
    viz_type: str = "dashboard"
) -> Dict[str, Any]:
    """获取结果可视化"""
    pass
```

## 🗂️ 数据模型

### 1. 方案模型 (Scenario)
```python
@dataclass
class Scenario:
    id: str
    name: str
    description: str
    scenario_type: str  # "battlefield", "logistics", "intelligence"
    parameters: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    created_by: str
    tags: List[str]
    status: str  # "draft", "active", "archived"
    version_history: List[VersionRef]
    current_version: str
```

### 2. 版本模型 (Version)
```python
@dataclass
class VersionInfo:
    id: str
    scenario_id: str
    parent_version: Optional[str]
    snapshot: ScenarioSnapshot
    created_at: datetime
    created_by: str
    commit_message: str
    changes: List[ChangeLog]
    tags: List[str]
    
@dataclass
class ScenarioSnapshot:
    id: str
    scenario_config: Dict[str, Any]
    parameter_values: Dict[str, Any]
    dependencies: List[Dependency]
    environment_config: Dict[str, Any]
    created_at: datetime
```

### 3. 推演结果模型 (SimulationResult)
```python
@dataclass
class SimulationResult:
    id: str
    scenario_id: str
    scenario_version: str
    parameters_used: Dict[str, Any]
    start_time: datetime
    end_time: datetime
    duration: float
    status: str  # "completed", "failed", "cancelled"
    
    # 结果数据
    raw_data: Dict[str, Any]
    metrics: Dict[str, float]
    events: List[SimulationEvent]
    logs: List[LogEntry]
    
    # 分析结果
    analysis: Optional[AnalysisResult]
    visualizations: Dict[str, Visualization]
    recommendations: List[Recommendation]
```

## 🚀 实现计划

### 阶段1: 基础沙箱和版本管理 (2周)
- [ ] 实现`SimulationSandbox`类
- [ ] 实现`ScenarioVersionManager`
- [ ] 基础API端点
- [ ] 临时存储系统

### 阶段2: 参数配置系统 (2周)
- [ ] 实现`ParameterConfigSystem`
- [ ] Web界面参数编辑器
- [ ] 参数验证规则引擎
- [ ] 实时预览功能

### 阶段3: 推演引擎集成 (2周)
- [ ] 集成现有Graphiti推演引擎
- [ ] 结果捕获和分析系统
- [ ] 对比分析功能
- [ ] What-if分析

### 阶段4: Web界面和用户体验 (2周)
- [ ] 完整的Web管理界面
- [ ] 拖拽式参数配置
- [ ] 实时结果可视化
- [ ] 多方案对比看板

## 📊 测试策略

### 1. 单元测试
```python
def test_simulation_sandbox_isolation():
    """测试沙箱隔离功能"""
    sandbox = SimulationSandbox("test_scenario", {})
    sandbox_id = await sandbox.create_sandbox()
    
    # 验证环境隔离
    assert sandbox.isolation_layer.is_isolated(sandbox_id)
    
    # 验证数据隔离
    test_data = {"test": "data"}
    await sandbox.store_data(test_data)
    assert not production_db.contains(test_data)

def test_version_management():
    """测试版本管理功能"""
    manager = ScenarioVersionManager()
    
    # 创建版本
    v1 = await manager.create_version({"param": "value1"})
    v2 = await manager.create_version({"param": "value2"}, v1.id)
    
    # 验证版本关系
    assert v2.parent_version == v1.id
    assert len(await manager.list_versions()) == 2
    
    # 测试回退
    await manager.revert_to_version(v1.id)
    current = await manager.get_current_version()
    assert current.config["param"] == "value1"
```

### 2. 集成测试
```python
def test_end_to_end_simulation():
    """端到端模拟推演测试"""
    # 创建方案
    scenario = await api.create_scenario({
        "name": "test_battle",
        "type": "battlefield"
    })
    
    # 配置参数
    await api.update_parameters(scenario.id, {
        "forces": {"red": 100, "blue": 150},
        "terrain": "mountainous"
    })
    
    # 执行推演
    result = await api.run_simulation(scenario.id)
    
    # 验证结果
    assert result.status == "completed"
    assert "metrics" in result
    assert result.duration > 0
    
    # 创建新版本
    await api.update_parameters(scenario.id, {
        "forces": {"red": 120, "blue": 130}
    })
    
    # 对比结果
    comparison = await api.compare_simulations([
        result.id,
        new_result.id
    ])
    
    assert "differences" in comparison
```

### 3. 性能测试
```python
def test_simulation_performance():
    """模拟推演性能测试"""
    # 并发推演测试
    start_time = time.time()
    
    tasks = []
    for i in range(10):
        task = asyncio.create_task(
            run_simulation(f"scenario_{i}")
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    end_time = time.time()
    
    # 验证性能指标
    total_time = end_time - start_time
    avg_time = total_time / len(results)
    
    assert avg_time < 30.0  # 平均推演时间 < 30秒
    assert all(r.status == "completed" for r in results)
```

## 🔒 安全考虑

### 1. 沙箱安全
- **资源限制**: CPU、内存、磁盘使用限制
- **网络隔离**: 限制沙箱的网络访问
- **文件系统隔离**: 只读基础镜像，写时复制
- **进程隔离**: 使用容器或命名空间隔离

### 2. 数据安全
- **临时数据**: 推演数据自动清理
- **敏感数据脱敏**: 生产数据在沙箱中脱敏处理
- **访问控制**: 基于角色的方案访问权限
- **审计日志**: 所有操作记录审计日志

### 3. 参数验证
- **输入验证**: 所有参数严格验证
- **范围限制**: 数值参数范围限制
- **依赖检查**: 参数间依赖关系验证
- **恶意代码检测**: 防止注入攻击

## 📈 监控与运维

### 1. 监控指标
```yaml
metrics:
  simulation:
    total_count: "模拟推演总数"
    success_rate: "推演成功率"
    avg_duration: "平均推演时长"
    concurrent_simulations: "并发推演数"
  
  sandbox:
    creation_time: "沙箱创建时间"
    resource_usage: "资源使用情况"
    isolation_breaches: "隔离违规次数"
  
  versioning:
    versions_created: "版本创建数"
    revert_operations: "回退操作数"
    storage_usage: "版本存储使用"
```

### 2. 告警规则
```yaml
alerts:
  simulation_failure_rate:
    condition: "success_rate < 95% over 5min"
    severity: "warning"
    
  sandbox_resource_exhaustion:
    condition: "memory_usage > 90% for 2min"
    severity: "critical"
    
  version_storage_limit:
    condition: "storage_usage > 80%"
    severity: "warning"
```

## 📋 版本历史

### v1.0.0 (2026-04-12)
- **初始版本**: 模拟推演引擎基础设计
- **核心功能**: 沙箱隔离、版本管理、参数配置
- **API设计**: 完整的REST API规范
- **测试策略**: 单元测试、集成测试、性能测试

### 待实现功能
2. **Web界面集成**: 完整的用户界面
3. **高级分析功能**: 机器学习结果分析
4. **协作功能**: 多用户协同推演
5. **模板系统**: 可复用的推演模板

---

**维护团队**: Graphiti架构组  
**文档状态**: 正式版  
**最后更新**: 2026-04-12