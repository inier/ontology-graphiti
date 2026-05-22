# 本体驱动分析决策平台 (ODAP) - L5-L6 接口层
> **部分**: 前端界面 + 管理后台 + API端点
> **版本**: 5.0.0 | **日期**: 2026-05-19
> **上级文档**: [ARCHITECTURE.md](ARCHITECTURE.md)
---
## 11. 前端界面架构

### 11.1 前端定位

前端界面是用户与系统的交互窗口，分为两大类：
- **领域前端**: 供不同角色（指挥官、情报分析员、操作员）使用
- **管理后台**: 供管理员配置系统、管理本体、审计日志

### 11.2 技术选型

| 组件 | 技术选型 | 理由 |
|------|---------|------|
| **框架** | React 19 + TypeScript | 组件化、类型安全、生态丰富 |
| **UI 库** | Ant Design 6 | 企业级组件、主题定制 |
| **状态管理** | Zustand | 轻量、支持持久化 |
| **图表** | ECharts + AntV G6 | 态势图 + 知识图谱可视化 |
| **地图** | CesiumJS | 3D 地理空间可视化 |
| **实时通信** | WebSocket + SSE | 实时推送领域变化 |
| **构建工具** | Vite | 快速启动、HMR |

### 11.3 移动优先与国际化策略

前端采用 **移动优先（Mobile First）** 的响应式设计策略，详见：

- [ADR-037: 移动优先与国际化策略](adr/ADR-037_frontend_mobile_first_i18n.md)
- [UI 设计 - 移动优先规范](ui/MOBILE_FIRST_DESIGN.md)
- [UI 设计 - 组件分级管理](ui/COMPONENT_HIERARCHY.md)

响应式断点设计：

| 设备 | 断点 | 布局 |
|------|------|------|
| 手机 | < 576px | 单栏 + 底部 Tab |
| 平板 | 576-1024px | 双栏 + 可收起侧边栏 |
| 笔记本 | 1024-1440px | 标准两栏 |
| 桌面 PC | 1440-1920px | 宽松两栏 |
| 大屏 | ≥ 1920px | 三栏布局 |

国际化支持：简体中文（zh-CN）、英语（en-US）


### 11.4 实时领域同步机制

```typescript
// frontend/services/websocket.ts
import { io, Socket } from 'socket.io-client';

class DomainSocket {
  private socket: Socket;

  constructor() {
    this.socket = io(BATTLEFIELD_WS_URL, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
    });
  }

  // 订阅领域实体变化
  onEntityChange(callback: (entity: EntityChange) => void) {
    this.socket.on('entity:changed', callback);
  }

  // 订阅情报更新
  onIntelUpdate(callback: (intel: IntelUpdate) => void) {
    this.socket.on('intel:updated', callback);
  }

  // 订阅打击结果
  onStrikeResult(callback: (result: StrikeResult) => void) {
    this.socket.on('strike:result', callback);
  }

  // 订阅 OODA 阶段
  onOODAProgress(callback: (progress: OODAProgress) => void) {
    this.socket.on('ooda:progress', callback);
  }
}

// 前端状态管理
interface DomainStore {
  entities: Map<string, Entity>;
  highlights: EntityChange[];  // 变更高亮
  pendingOrders: Order[];

  // 添加变更到高亮队列
  addHighlight(change: EntityChange) {
    this.highlights.push(change);
    // 3秒后自动移除高亮
    setTimeout(() => {
      this.highlights = this.highlights.filter(h => h.id !== change.id);
    }, 3000);
  }
}
```

### 11.5 一键引用功能

```typescript
// 前端：快速将图谱信息添加到问答
const QuickQuoteButton = ({ entityId, entityName }) => {
  const addToContext = () => {
    // 将选中的实体信息添加到 AI 助手的上下文
    const entityContext = {
      id: entityId,
      name: entityName,
      timestamp: Date.now(),
      source: 'graphiti'
    };

    // 发送到 AI 助手组件
    eventBus.emit('ai:addContext', entityContext);

    // Toast 提示
    message.success(`已添加 "${entityName}" 到问答上下文`);
  };

  return (
    <Button
      icon={<PlusCircleOutlined />}
      onClick={addToContext}
      size="small"
    >
      添加到问答
    </Button>
  );
};
```

### 11.6 问答图表系统（可扩展）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          问答图表系统 (Q&A Chart System)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   图表渲染器    │  │   图表注册表    │  │   图表编辑器    │             │
│  │  ChartRenderer  │  │  ChartRegistry  │  │  ChartEditor    │             │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤             │
│  │ • ECharts      │  │ • 柱状图       │  │ • 配置生成     │             │
│  │ • AntV G6      │  │ • 折线图       │  │ • 实时预览     │             │
│  │ • Plotly       │  │ • 饼图         │  │ • 代码导出     │             │
│  │ • 自定义渲染   │  │ • 散点图       │  │ • 模板库      │             │
│  │                │  │ • 雷达图       │  │               │             │
│  │                │  │ • 桑基图       │  │               │             │
│  │                │  │ • 力导向图     │  │               │             │
│  │                │  │ • 热力图       │  │               │             │
│  │                │  │ • 地图         │  │               │             │
│  │                │  │ • 关系图谱     │  │               │             │
│  │                │  │ • 自定义图表   │  │               │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 11.6.1 图表类型注册

```typescript
// charts/chart-registry.ts

interface ChartDefinition {
  type: string;                      // 图表类型标识
  name: string;                       // 显示名称
  description: string;               // 描述
  icon: string;                      // 图标
  renderer: ChartRenderer;           // 渲染器类型
  defaultConfig: ChartConfig;       // 默认配置
  dataSchema: DataSchema;            // 数据模式
  capabilities: ChartCapability[];   // 能力列表
}

interface ChartCapability {
  type: 'animation' | 'export' | 'interactive' | 'realtime';
  enabled: boolean;
}

class ChartRegistry {
  private charts: Map<string, ChartDefinition> = new Map();

  register(definition: ChartDefinition): void {
    // 1. 验证定义
    this.validateDefinition(definition);

    // 2. 注册图表
    this.charts.set(definition.type, definition);

    // 3. 发布事件
    eventBus.publish(new ChartRegisteredEvent(definition.type));
  }

  getChart(type: string): ChartDefinition | undefined {
    return this.charts.get(type);
  }

  getAllCharts(): ChartDefinition[] {
    return Array.from(this.charts.values());
  }
}

// 注册内置图表
const registry = new ChartRegistry();

// 内置图表：柱状图
registry.register({
  type: 'bar',
  name: '柱状图',
  description: '用于对比分类数据',
  icon: 'bar-chart',
  renderer: 'echarts',
  defaultConfig: {
    xAxis: { type: 'category' },
    yAxis: { type: 'value' },
    series: [{ type: 'bar' }]
  },
  dataSchema: {
    required: ['categories', 'values'],
    optional: ['series', 'labels']
  },
  capabilities: [
    { type: 'animation', enabled: true },
    { type: 'export', enabled: true },
    { type: 'interactive', enabled: true }
  ]
});

// 内置图表：知识图谱
registry.register({
  type: 'knowledge-graph',
  name: '知识图谱',
  description: '展示实体关系网络',
  icon: 'apartment',
  renderer: 'antv-g6',
  defaultConfig: {
    layout: { type: 'force-directed' },
    nodeSize: 20,
    edgeWidth: 1
  },
  dataSchema: {
    required: ['nodes', 'edges'],
    optional: ['categories', 'weights']
  },
  capabilities: [
    { type: 'animation', enabled: true },
    { type: 'export', enabled: true },
    { type: 'interactive', enabled: true }
  ]
});
```

### 11.7 用户认知引擎

**核心功能**：构建用户端界面，站在不同使用角色的角度，观测到自己的问题被意图识别处理到最后返回结果的可解释过程。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         用户认知引擎                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │  Intent Recognizer│   │  Knowledge Navigator│  │  Explanation Engine│      │
│  │  • 意图识别     │    │  • 知识导航     │    │  • 过程解释     │         │
│  │  • 需求解析     │    │  • 推理路径     │    │  • 可解释性     │         │
│  │  • 角色识别     │    │  • 本体查询     │    │  • 可视化解释   │         │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│           │                     │                     │                    │
│           └─────────────────────┼─────────────────────┘                    │
│                                 ▼                                          │
│                    ┌────────────────────────┐                              │
│                    │  Role-based View       │                              │
│                    │  • 指挥官视图         │                              │
│                    │  • 情报分析员视图     │                              │
│                    │  • 操作员视图         │                              │
│                    └──────────┬─────────────┘                              │
│                               │                                            │
│                               ▼                                            │
│                    ┌────────────────────────┐                              │
│                    │  Result Presenter      │                              │
│                    │  • 结果呈现           │                              │
│                    │  • 多模态展示         │                              │
│                    │  • 交互反馈           │                              │
│                    └────────────────────────┘                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 11.7.1 处理流程

| 阶段 | 描述 | 输出 |
|------|------|------|
| **问题解析** | 识别用户意图和需求 | 意图分类、需求提取 |
| **知识检索** | 基于本体查询相关知识 | 知识图谱查询结果 |
| **推理过程** | 基于本体进行推理 | 推理路径、决策依据 |
| **结果生成** | 生成符合用户角色的结果 | 个性化结果 |
| **解释生成** | 提供可理解的过程解释 | 可视化解释 |
| **反馈收集** | 收集用户反馈 | 反馈数据 |

#### 11.7.2 角色基于的视图

| 角色 | 关注点 | 视图特点 |
|------|--------|----------|
| **指挥官** | 决策制定、全局态势 | 战略层面、决策建议、风险分析 |
| **情报分析员** | 情报收集、分析 | 详细数据、趋势分析、异常检测 |
| **操作员** | 执行操作、状态监控 | 执行界面、状态反馈、操作指导 |
| **管理员** | 系统配置、监控 | 管理界面、审计日志、系统状态 |

#### 11.7.3 技术实现

```typescript
// services/user_cognition_engine.ts

class UserCognitionEngine {
  private intentRecognizer: IntentRecognizer;
  private knowledgeNavigator: KnowledgeNavigator;
  private explanationEngine: ExplanationEngine;
  private roleBasedView: RoleBasedView;
  private resultPresenter: ResultPresenter;

  constructor() {
    this.intentRecognizer = new IntentRecognizer();
    this.knowledgeNavigator = new KnowledgeNavigator();
    this.explanationEngine = new ExplanationEngine();
    this.roleBasedView = new RoleBasedView();
    this.resultPresenter = new ResultPresenter();
  }

  async processUserQuery(userQuery: string, userRole: string) {
    // 1. 意图识别
    const intent = await this.intentRecognizer.recognize(userQuery, userRole);
    
    // 2. 知识检索
    const knowledge = await this.knowledgeNavigator.navigate(
      intent, 
      userRole
    );
    
    // 3. 推理过程
    const reasoning = await this.knowledgeNavigator.reason(
      intent, 
      knowledge
    );
    
    // 4. 生成结果
    const result = await this.resultPresenter.generate(
      intent, 
      knowledge, 
      reasoning, 
      userRole
    );
    
    // 5. 生成解释
    const explanation = await this.explanationEngine.generate(
      intent, 
      knowledge, 
      reasoning, 
      result
    );
    
    // 6. 角色基于的视图
    const view = this.roleBasedView.getView(
      userRole, 
      result, 
      explanation
    );
    
    return {
      intent,
      knowledge,
      reasoning,
      result,
      explanation,
      view
    };
  }
}

```

#### 11.6.2 图表渲染器

```typescript
// charts/chart-renderer.ts

interface ChartRenderer {
  type: string;
  render(container: HTMLElement, config: ChartConfig, data: ChartData): void;
  update(config: ChartConfig, data: ChartData): void;
  resize(): void;
  export(format: 'png' | 'svg' | 'pdf'): Promise<Blob>;
  destroy(): void;
}

class EChartsRenderer implements ChartRenderer {
  type = 'echarts';
  private chart: ECharts.EChartsOption | null = null;

  render(container: HTMLElement, config: ChartConfig, data: ChartData): void {
    this.chart = echarts.init(container);
    this.update(config, data);
  }

  update(config: ChartConfig, data: ChartData): void {
    if (!this.chart) return;

    const option = this.buildOption(config, data);
    this.chart.setOption(option, { notMerge: true });
  }

  private buildOption(config: ChartConfig, data: ChartData): ECharts.EChartsOption {
    // 动态构建 ECharts 配置
    return {
      ...config,
      series: data.series.map(s => ({
        ...config.series?.[0],
        data: s.data
      })),
      xAxis: {
        ...config.xAxis,
        data: data.categories
      }
    };
  }

  export(format: 'png' | 'svg' | 'pdf'): Promise<Blob> {
    return this.chart!.getConnectedDataURL({
      type: format === 'pdf' ? 'png' : format,
      pixelRatio: 2,
      backgroundColor: '#fff'
    });
  }
}

// 自定义图表渲染器注册
ChartRendererFactory.register('echarts', new EChartsRenderer());
ChartRendererFactory.register('antv-g6', new AntVG6Renderer());
ChartRendererFactory.register('plotly', new PlotlyRenderer());
```

#### 11.6.3 会话问答图表展示

```typescript
// components/ChatChart.tsx

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  charts?: ChartRenderRequest[];
  timestamp: Date;
}

const ChatChart: React.FC<{ message: ChatMessage }> = ({ message }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [renderer, setRenderer] = useState<ChartRenderer | null>(null);

  // 加载图表渲染器
  useEffect(() => {
    if (message.charts && message.charts.length > 0) {
      const chartType = message.charts[0].type;
      const definition = chartRegistry.getChart(chartType);

      if (definition) {
        const rendererInstance = ChartRendererFactory.create(definition.renderer);
        setRenderer(rendererInstance);
      }
    }
  }, [message.charts]);

  // 渲染图表
  useEffect(() => {
    if (renderer && chartContainerRef.current && message.charts) {
      renderer.render(
        chartContainerRef.current,
        message.charts[0].config,
        message.charts[0].data
      );
    }

    return () => renderer?.destroy();
  }, [renderer, message.charts]);

  return (
    <Card className="chat-chart-card">
      {message.charts?.map((chart, index) => (
        <div key={index} className="chart-container">
          <div className="chart-header">
            <span className="chart-type">{chart.type}</span>
            <Space>
              <Button size="small" icon={<FullscreenOutlined />}>全屏</Button>
              <Button size="small" icon={<DownloadOutlined />}>导出</Button>
            </Space>
          </div>
          <div ref={chartContainerRef} className="chart-canvas" />
        </div>
      ))}
    </Card>
  );
};
```

---


## 12. 管理后台架构

### 12.1 管理后台定位

管理后台供系统管理员使用，实现**可配置、可扩展、可维护**的管理能力：

| 模块 | 功能 | 核心特性 |
|------|------|----------|
| **角色配置** | 自定义角色、技能绑定、策略关联 | 热生效、版本管理 |
| **本体管理** | 图谱可视化、节点/边编辑、数据导入 | 实时预览、多数据源 |
| **策略管理** | OPA 策略编辑（Markdown → Rego） | 版本历史、差异对比 |
| **规则管理** | 业务规则 CRUD、规则组合、条件链 | 规则测试沙箱 |
| **技能管理** | 技能注册、启用/禁用、依赖管理 | 自动热加载 |
| **数据源管理** | 结构化/非结构化数据源接入 | 数据预览、脱敏配置 |
| **审计日志** | 全链路日志查询、导出、分析 | 多维度筛选 |
| **系统配置** | 分组配置、配置版本、灰度发布 | 变更追踪 |

### 12.2 配置组合架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           配置中心 (Configuration Hub)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        角色 (Role) 配置层                             │   │
│  │                                                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │ 指挥官     │  │ 情报分析员  │  │ 操作员      │  │ 自定义角色  │  │   │
│  │  │ Commander   │  │ Intelligence│  │ Operations  │  │ Custom      │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │   │
│  │         │                │                │                │         │   │
│  │         ▼                ▼                ▼                ▼         │   │
│  │  ┌─────────────────────────────────────────────────────────────┐       │   │
│  │  │                   技能 (Skill) 绑定                          │       │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │       │   │
│  │  │  │打击技能 │ │分析技能 │ │查询技能 │ │可视化技能│  ...     │       │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │       │   │
│  │  └─────────────────────────────────────────────────────────────┘       │   │
│  │                              │                                          │   │
│  │                              ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────┐       │   │
│  │  │                   策略 (Policy) 绑定                         │       │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │       │   │
│  │  │  │授权策略 │ │执行策略 │ │数据策略 │ │审计策略 │  ...     │       │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │       │   │
│  │  └─────────────────────────────────────────────────────────────┘       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 配置组合数据结构

```python
# models/config_models.py

@dataclass
class Role:
    id: str
    name: str                          # 角色名称
    description: str                   # 角色描述
    base_type: str                     # 基类型: commander/intelligence/operations
    skills: List[str]                 # 绑定技能列表
    policies: List[str]                # 绑定策略列表
    data_sources: List[str]            # 可访问数据源
    priority: int                      # 优先级
    status: str                       # enabled/disabled
    version: str                      # 配置版本
    created_at: datetime
    updated_at: datetime
    created_by: str
    metadata: Dict[str, Any]           # 扩展元数据

@dataclass
class SkillBinding:
    role_id: str
    skill_id: str
    priority: int                      # 同角色内技能优先级
    params: Dict[str, Any]            # 技能参数覆盖
    enabled: bool
    conditions: List[Condition]       # 触发条件

@dataclass
class PolicyBinding:
    role_id: str
    policy_id: str
    effect: str                       # allow/deny
    conditions: List[Condition]       # 生效条件
    priority: int                      # 冲突时优先级

@dataclass
class ConfigurationProfile:
    id: str
    name: str                          # 配置集名称
    description: str
    roles: List[Role]                  # 角色列表
    global_skills: List[str]           # 全局技能
    global_policies: List[str]          # 全局策略
    data_sources: List[DataSource]      # 数据源配置
    is_active: bool                    # 是否激活
    is_default: bool                   # 是否默认配置
    validation_status: str             # 验证状态
```

### 12.4 配置热生效机制

```python
# services/config_hot_reload.py

class ConfigurationHotReload:
    """配置热生效服务"""

    def __init__(self, event_bus: EventBus, cache: Cache):
        self.event_bus = event_bus
        self.cache = cache
        self.subscribers = []

    async def apply_changes(self, change: ConfigChange) -> ApplyResult:
        # 1. 验证配置合法性
        validation = await self.validate_config(change)
        if not validation.is_valid:
            return ApplyResult(success=False, errors=validation.errors)

        # 2. 预览变更影响
        impact = await self.analyze_impact(change)
        if impact.has_critical_changes:
            # 需要审批流程
            await self.request_approval(impact)

        # 3. 生成变更批次
        batch = ChangeBatch.create(change)

        # 4. 原子性应用变更
        async with self.transaction():
            await self.apply_to_database(batch)
            await self.sync_to_cache(batch)
            await self.notify_subscribers(batch)

        # 5. 记录审计日志
        await self.audit_log.record(change)

        return ApplyResult(success=True, batch_id=batch.id)

    async def notify_subscribers(self, batch: ChangeBatch):
        """通知订阅者配置变更"""
        for subscriber in self.subscribers:
            await subscriber.on_config_changed(batch)


class ConfigChangeSubscriber(ABC):
    """配置变更订阅者接口"""

    @abstractmethod
    async def on_config_changed(self, batch: ChangeBatch):
        pass


class SkillHotReload(ConfigChangeSubscriber):
    """技能热加载"""

    async def on_config_changed(self, batch: ChangeBatch):
        for change in batch.changes:
            if change.type == 'skill':
                if change.action == 'enable':
                    await self.skill_registry.enable(change.target_id)
                elif change.action == 'disable':
                    await self.skill_registry.disable(change.target_id)
                elif change.action == 'create':
                    await self.skill_registry.register(
                        change.target_id,
                        change.payload
                    )


class PolicyHotReload(ConfigChangeSubscriber):
    """策略热加载"""

    async def on_config_changed(self, batch: ChangeBatch):
        for change in batch.changes:
            if change.type == 'policy':
                await self.opa_client.reload_policy(change.target_id)
```

### 12.5 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           管理后台 (Admin Dashboard)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   模拟数据      │  │   本体管理      │  │   策略管理      │             │
│  │   管理         │  │                 │  │                 │             │
│  │                 │  │                 │  │                 │             │
│  │ • 事件生成器   │  │ • 节点浏览      │  │ • Markdown 编辑 │             │
│  │ • 事件队列     │  │ • 属性查看      │  │ • Rego 预览     │             │
│  │ • 手工采用     │  │ • 边关系查看    │  │ • 策略启停      │             │
│  │ • 批量导入     │  │ • 溯源日志      │  │ • 版本历史      │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   角色管理      │  │   审计日志      │  │   系统配置      │             │
│  │                 │  │                 │  │                 │             │
│  │ • 角色 CRUD    │  │ • 日志查询      │  │ • 配置分组      │             │
│  │ • Skill 分配   │  │ • 高级筛选      │  │ • 可视化编辑    │             │
│  │ • OPA 策略绑定 │  │ • 导出报表      │  │ • 说明文档      │             │
│  │ • 生效控制     │  │ • 溯源分析      │  │ • 版本对比      │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.6 模拟数据管理

```typescript
// 后端: simulation_controller.py
class SimulationController {
  // 生成模拟事件
  async generateEvents(config: SimulationConfig): Promise<SimulationResult> {
    const events = await this.eventGenerator.generate({
      region: config.region,
      density: config.density,
      types: config.eventTypes,
      timeRange: config.timeRange,
    });

    return {
      eventCount: events.length,
      events: events.map(e => ({
        id: e.id,
        type: e.type,
        description: e.description,
        source: 'simulation',
        timestamp: e.timestamp,
        status: 'pending',  // pending | adopted | rejected
      })),
    };
  }

  // 手工采用模拟事件
  async adoptEvent(eventId: string): Promise<void> {
    const event = await this.getEvent(eventId);

    // 将事件写入 Graphiti
    await this.graphiti.addEpisode({
      name: `Adopted_Simulation_${eventId}`,
      episode_body: event.description,
      source: 'simulation_adopted',
      time_stamp: event.timestamp,
    });

    // 更新事件状态
    event.status = 'adopted';
    await this.eventStore.save(event);
  }
}

// 前端: SimulationDashboard
const SimulationDashboard: React.FC = () => {
  const [events, setEvents] = useState<SimulationEvent[]>([]);
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);

  return (
    <Card title="模拟领域事件">
      <Space direction="vertical" style={{ width: '100%' }}>
        <Row gutter={16}>
          <Col span={8}>
            <Button type="primary" onClick={generateEvents}>
              生成模拟事件
            </Button>
          </Col>
          <Col span={8}>
            <Button
              type="primary"
              disabled={selectedEvents.length === 0}
              onClick={adoptSelected}
            >
              批量采用 ({selectedEvents.length})
            </Button>
          </Col>
        </Row>

        <Table
          dataSource={events}
          rowSelection={{
            selectedRowKeys: selectedEvents,
            onChange: (keys) => setSelectedEvents(keys as string[]),
          }}
          columns={[
            { title: '类型', dataIndex: 'type' },
            { title: '描述', dataIndex: 'description' },
            { title: '时间', dataIndex: 'timestamp' },
            { title: '状态', dataIndex: 'status', render: (s) => <StatusTag>{s}</StatusTag> },
            {
              title: '操作',
              render: (_, record) => (
                <Space>
                  <Button size="small" onClick={() => adoptEvent(record.id)}>采用</Button>
                  <Button size="small" onClick={() => viewDetail(record.id)}>详情</Button>
                </Space>
              ),
            },
          ]}
        />
      </Space>
    </Card>
  );
};
```

### 12.7 本体图谱管理

```typescript
// 前端: OntologyGraphViewer
const OntologyGraphViewer: React.FC = () => {
  const [selectedNode, setSelectedNode] = useState<EntityNode | null>(null);
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });

  // 加载图谱数据
  useEffect(() => {
    loadGraphData().then(setGraphData);
  }, []);

  return (
    <Split horizontal defaultSizes={[300, 700]}>
      {/* 左侧：节点列表 */}
      <div>
        <Tree
          treeData={buildEntityTree(graphData.nodes)}
          onSelect={(keys) => {
            const node = graphData.nodes.find(n => n.id === keys[0]);
            setSelectedNode(node);
          }}
        />
      </div>

      {/* 中间：图谱可视化 */}
      <div>
        <AntVGraph
          data={graphData}
          onNodeClick={(node) => setSelectedNode(node.data)}
          layout="force"
          animate
        />
      </div>

      {/* 右侧：属性面板 */}
      <div>
        {selectedNode ? (
          <EntityDetailPanel
            entity={selectedNode}
            onUpdate={handleEntityUpdate}
          />
        ) : (
          <Empty description="请选择节点查看详情" />
        )}
      </div>
    </Split>
  );
};

// 本体溯源日志展示
const TraceLogPanel: React.FC<{ entityId: string }> = ({ entityId }) => {
  const [logs, setLogs] = useState<TraceLog[]>([]);

  useEffect(() => {
    loadTraceLogs(entityId).then(setLogs);
  }, [entityId]);

  return (
    <Timeline mode="left">
      {logs.map((log) => (
        <Timeline.Item
          key={log.id}
          color={log.type === 'external' ? 'blue' : 'green'}
          label={formatTime(log.timestamp)}
        >
          <Card size="small">
            <Space>
              <Tag>{log.type}</Tag>
              <Text strong>{log.description}</Text>
            </Space>
            {log.source && (
              <div>
                <Text type="secondary">来源: {log.source}</Text>
              </div>
            )}
          </Card>
        </Timeline.Item>
      ))}
    </Timeline>
  );
};
```

### 12.8 OPA 策略管理（Markdown → Rego）

```typescript
// 后端: policy_controller.py
class PolicyController {
  // Markdown 转 Rego
  async markdownToRego(markdown: string): Promise<string> {
    return this.markdownConverter.convert(markdown);
  }

  // 保存策略
  async savePolicy(policy: Policy): Promise<void> {
    // 1. Markdown 转 Rego
    const rego = await this.markdownToRego(policy.markdown);

    // 2. 语法验证
    const validation = await this.opa.validate(rego);
    if (!validation.valid) {
      throw new PolicyValidationError(validation.errors);
    }

    // 3. 保存到文件系统
    await this.policyStore.save(policy.name, {
      markdown: policy.markdown,
      rego: rego,
      version: Date.now(),
      status: policy.status,  // draft | enabled | disabled
    });

    // 4. 如果启用，热更新 OPA
    if (policy.status === 'enabled') {
      await this.opa.reloadPolicies();
    }
  }

  // 手动/自动生效控制
  async setPolicyStatus(policyId: string, status: 'enabled' | 'disabled'): Promise<void> {
    await this.policyStore.updateStatus(policyId, status);

    if (status === 'enabled') {
      await this.opa.reloadPolicies();
    }
  }
}

// Markdown 策略示例
const markdownPolicy = `
# 打击权限策略

## 基本规则

允许条件：
1. 操作用户具有 commander 角色
2. 目标不在保护名单中（民用、医疗、历史遗迹）
3. 武器参数满足要求

### 12.3 Rego 策略示例

\`\`\`rego
package policies.attack

allow if {
    input.action == "attack_target"
    input.commander_id != ""
    not is_protected_target(input.target)
}

is_protected_target(target) if {
    target.category == "civilian"
}
\`\`\`
`;
```

---


## C. API 端点

### C.1 本体管理 API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/ontology/workspace` | POST | 创建工作空间 |
| `/api/v1/ontology/workspaces` | GET | 列出工作空间 |
| `/api/v1/ontology/workspace/{id}` | DELETE | 删除工作空间 |
| `/api/v1/ontology/write` | POST | 热写入 OntologyDocument |
| `/api/v1/ontology/query` | GET | 图谱查询 |
| `/api/v1/ontology/versions/{ws_id}` | GET | 版本列表 |
| `/api/v1/ontology/version/switch` | POST | 切换版本 |
| `/api/v1/ontology/version/rollback` | POST | 回退版本 |
| `/api/v1/ontology/export` | POST | 导出 |
| `/api/v1/ontology/import` | POST | 导入 |

### C.2 模拟器 API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/simulator/scenario` | POST | 创建场景 |
| `/api/v1/simulator/run` | POST | 启动推演 |
| `/api/v1/simulator/pause/{id}` | POST | 暂停 |
| `/api/v1/simulator/resume/{id}` | POST | 恢复 |
| `/api/v1/simulator/result/{id}` | GET | 获取结果 |

### C.3 Agent API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/agent/mission` | POST | 创建任务（触发 OODA） |
| `/api/v1/agent/mission/{id}` | GET | 获取任务状态 |
| `/api/v1/agent/mission/{id}/stream` | GET | SSE 流式响应 |

### C.4 工作空间 API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/workspace` | POST | 创建工作空间 |
| `/api/v1/workspace` | GET | 列出工作空间 |
| `/api/v1/workspace/{id}` | GET | 工作空间详情 |
| `/api/v1/workspace/{id}/switch` | POST | 切换工作空间 |

### C.5 系统 API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/system/health` | GET | 健康检查 |
| `/api/v1/system/metrics` | GET | 系统指标 |

### C.6 WebSocket

| 端点 | 协议 | 描述 |
|------|------|------|
| `/ws/events` | WebSocket | 实时事件流（模拟推演 + 本体更新） |


---

> **附录E 已拆分**: Phase 4-5 详细规划已移至 [PHASE4_5_PLAN.md](PHASE4_5_PLAN.md)

---

## 附录 D.4: OMS / 对象服务 / 动作服务 API (v5.0.0 新增)

### D.4.1 本体元数据服务 (OMS)

| 端点 | 方法 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/ontology/oms/object-types` | GET | 列出所有对象类型 | `?active_only=true` | `ObjectTypeDefinition[]` |
| `/api/ontology/oms/object-types` | POST | 创建对象类型 | `OntologySchemaCreate` | `ObjectTypeDefinition` |
| `/api/ontology/oms/object-types/{id}` | GET | 获取对象类型 | - | `ObjectTypeDefinition` |
| `/api/ontology/oms/object-types/{id}` | PUT | 更新对象类型 | `OntologySchemaUpdate` | `ObjectTypeDefinition` |
| `/api/ontology/oms/object-types/{id}` | DELETE | 删除对象类型 | - | `{message}` |
| `/api/ontology/oms/action-types` | GET | 列出所有动作类型 | `?target_type=Unit` | `ActionTypeDefinition[]` |
| `/api/ontology/oms/action-types` | POST | 创建动作类型 | `ActionTypeCreate` | `ActionTypeDefinition` |
| `/api/ontology/oms/action-types/{id}` | GET/PUT/DELETE | 动作类型 CRUD | - | `ActionTypeDefinition` |
| `/api/ontology/oms/object-types/{id}/actions/{aid}` | POST | 绑定动作到对象类型 | - | `{message}` |
| `/api/ontology/oms/object-types/{id}/actions/{aid}` | DELETE | 解绑动作 | - | `{message}` |

### D.4.2 对象服务 (OSv2)

| 端点 | 方法 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/objects/query` | POST | 结构化对象查询 | `ObjectQuery` | `ObjectQueryResponse` |
| `/api/objects/semantic` | POST | 语义对象查询 | `SemanticQuery` | `SemanticQueryResponse` |
| `/api/objects/{id}` | GET | 获取单个对象 | `?object_type=Unit` | `ObjectQueryResult` |

### D.4.3 动作服务 (Action Service)

| 端点 | 方法 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/actions/submit` | POST | 提交动作 | `ActionRequest` | `ActionRecord` |
| `/api/actions/{id}/approve` | POST | 审批并执行 | `ActionApproval` | `ActionRecord` |
| `/api/actions/records` | GET | 查询动作记录 | `?status=pending&limit=50` | `ActionRecord[]` |
| `/api/actions/records/{id}` | GET | 获取动作详情 | - | `ActionRecord` |
| `/api/actions/target/{id}` | GET | 按目标对象查询 | `?limit=20` | `ActionRecord[]` |

### D.4.4 前端新增组件

| 组件 | 文件 | 说明 |
|------|------|------|
| `ActionPanel` | `modules/ontology/components/ActionPanel.tsx` | 动作管理面板：记录列表、提交表单、审批/执行、详情抽屉 |
| 前端 API 方法 | `modules/shared/services/api.ts` | 新增 20+ API 方法覆盖 OMS/OSv2/Action Service |

---

*文档版本: 5.0.0 | 最后更新: 2026-05-19 | 作者: 软件架构师*
*附录D.4 (OMS/对象服务/动作服务 API) 于 2026-05-19 新增*

