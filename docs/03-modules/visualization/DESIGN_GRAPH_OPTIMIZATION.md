# 本体图谱可视化优化设计文档

> **版本**: 2.0.0 | **日期**: 2026-05-06 | **状态**: 设计稿
> **依赖**: [ADR-045 前端可视化选型](../../07-adr/ADR-045_frontend_visualization_g6_leaflet.md), [本体管理设计](../ontology/DESIGN.md)

---

## 1. 问题诊断

### 1.1 当前症状

| 问题 | 表现 | 根因 |
|------|------|------|
| **视觉混乱** | 所有节点同质化严重，难以区分实体类型 | 未设计节点类型-视觉映射 |
| **信息过载** | 大图谱渲染后变成一团线团 | 缺分层展示，一次性渲染所有节点 |
| **交互缺失** | 选中节点无详情，无筛选，无搜索 | 未实现图谱交互系统 |
| **关系不清** | 连线交叉严重，方向性不可见 | 未配置合适的布局算法和边样式 |
| **时序缺失** | 无法看到图谱的时间演变 | 未使用Graphiti的transaction_time/valid_time |
| **与问答割裂** | 图谱和问答是两个独立页面 | 未设计图谱-问答双向联动 |

### 1.2 根因分析

当前OntologyBuilder页面仅使用基础G6实例+默认配置，未针对本体图谱场景做深度定制。核心缺失：
- 节点类型→视觉属性的映射规则
- 分层渲染策略（不同缩放级别显示不同粒度）
- 节点/边交互的事件系统
- 与右侧详情面板的联动机制

---

## 2. 优化方案总览

### 2.1 三层可视化架构

```
┌──────────────────────────────────────────────────────────────────┐
│  第1层：摘要视图 (Summary View) - 缩放 0.1x~0.5x                 │
│  按实体类型分组聚合，每组显示为气泡卡片，含数量和占比              │
├──────────────────────────────────────────────────────────────────┤
│  第2层：上下文视图 (Context View) - 缩放 0.5x~1.5x               │
│  显示选中实体的2跳关系子图，按布局算法排列                        │
├──────────────────────────────────────────────────────────────────┤
│  第3层：详情视图 (Detail View) - 缩放 > 1.5x                     │
│  单个实体完整展示：所有属性、关联实体、时间序列、关联事件          │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 节点视觉映射规则

```typescript
// 节点类型→视觉属性映射配置
const NODE_TYPE_VISUAL_MAP: Record<string, NodeVisualConfig> = {
  Campaign: {
    shape: 'hexagon',        // 六边形：战役级实体
    size: 48,
    fill: '#1a1a2e',
    stroke: '#e94560',
    icon: '🏴',
    labelPosition: 'center'
  },
  Unit: {
    shape: 'rounded-rect',
    size: 40,
    fill: '#16213e',
    stroke: '#0f3460',
    icon: '⚔️',
    labelPosition: 'bottom'
  },
  Weapon: {
    shape: 'triangle',
    size: 32,
    fill: '#533483',
    stroke: '#e94560',
    icon: '🎯',
    labelPosition: 'bottom'
  },
  Intel: {
    shape: 'circle',
    size: 28,
    fill: '#1a1a2e',
    stroke: '#ffd700',
    icon: '📡',
    labelPosition: 'right'
  },
  StrikeOrder: {
    shape: 'diamond',
    size: 36,
    fill: '#e94560',
    stroke: '#ffd700',
    icon: '💥',
    labelPosition: 'bottom'
  },
  Location: {
    shape: 'rect',
    size: 24,
    fill: '#0f3460',
    stroke: '#53a8b6',
    icon: '📍',
    labelPosition: 'bottom'
  }
}
```

### 2.3 关系线型映射

```typescript
const EDGE_TYPE_VISUAL_MAP: Record<string, EdgeVisualConfig> = {
  EQUIPPED_WITH: {
    stroke: '#53a8b6',
    lineWidth: 2,
    lineDash: [],
    arrow: true,
    label: '装备'
  },
  COMMANDED_BY: {
    stroke: '#e94560',
    lineWidth: 2,
    lineDash: [4, 4],
    arrow: true,
    label: '指挥'
  },
  LOCATED_AT: {
    stroke: '#ffd700',
    lineWidth: 1,
    lineDash: [2, 2],
    arrow: false,
    label: '位置'
  },
  TARGETS: {
    stroke: '#ff6b6b',
    lineWidth: 3,
    lineDash: [],
    arrow: true,
    label: '目标'
  },
  DERIVED_FROM: {
    stroke: '#a29bfe',
    lineWidth: 1,
    lineDash: [6, 3],
    arrow: true,
    label: '来源'
  }
}
```

---

## 3. 核心技术实现

### 3.1 基于AntV G6 v5的实例化

```typescript
import { Graph, NodeEvent } from '@antv/g6'

const initOntologyGraph = (container: HTMLElement) => {
  const graph = new Graph({
    container,
    autoFit: 'view',
    padding: [30, 30, 30, 30],

    node: {
      type: 'rect',                    // 默认节点类型
      style: {
        size: (d) => NODE_TYPE_VISUAL_MAP[d.type]?.size ?? 30,
        fill: (d) => NODE_TYPE_VISUAL_MAP[d.type]?.fill ?? '#1a1a2e',
        stroke: (d) => NODE_TYPE_VISUAL_MAP[d.type]?.stroke ?? '#333',
        labelText: (d) => d.label ?? d.id,
        labelBackground: true,
        labelPlacement: 'bottom'
      }
    },
    edge: {
      type: 'cubic-horizontal',        // 水平弧线边
      style: {
        stroke: (d) => EDGE_TYPE_VISUAL_MAP[d.type]?.stroke ?? '#555',
        lineWidth: (d) => EDGE_TYPE_VISUAL_MAP[d.type]?.lineWidth ?? 1,
        endArrow: true,
        labelText: (d) => EDGE_TYPE_VISUAL_MAP[d.type]?.label ?? d.type
      }
    },
    layout: {
      type: 'force',
      preventOverlap: true,
      nodeSpacing: 60,
      linkDistance: 150,
      animated: true
    },
    behaviors: [
      'zoom-canvas',                   // 滚轮缩放
      'drag-canvas',                   // 拖拽画布
      'drag-element',                  // 拖拽节点
      'click-select',                  // 点击选择
      {
        type: 'hover-activate',        // 悬停高亮邻居
        degree: 1
      },
      {
        type: 'tooltip',               // tooltip
        trigger: 'hover',
        getContent: (event, items) => getTooltipContent(items[0])
      }
    ],
    animation: {
      duration: 500
    },
    transforms: ['process-parallel-edges'] // 多边并行处理
  })

  applyEventHandlers(graph)
  return graph
}
```

### 3.2 事件处理系统

```typescript
const applyEventHandlers = (graph: Graph) => {
  // 节点点击 → 选中+更新右侧详情面板
  graph.on(NodeEvent.CLICK, (evt) => {
    const { target } = evt
    graph.setElementState({ [target.id]: 'selected' }, 'selected')
    // 触发外部事件，通知右侧面板更新
    eventBus.emit('ontology:node:select', {
      nodeId: target.id,
      nodeData: graph.getNodeData(target.id)
    })
  })

  // 边点击 → 显示关系详情
  graph.on('edge:click', (evt) => {
    const { target } = evt
    eventBus.emit('ontology:edge:select', {
      edgeId: target.id,
      edgeData: graph.getEdgeData(target.id)
    })
  })

  // 画布空白点击 → 取消选中
  graph.on('canvas:click', () => {
    graph.setElementState({}, 'selected')
    eventBus.emit('ontology:deselect')
  })

  // 右键菜单
  graph.on('node:contextmenu', (evt) => {
    const { target, canvas } = evt
    showContextMenu(canvas.getCanvasByViewport({ x: evt.client.x, y: evt.client.y }), target)
  })
}
```

### 3.3 筛选搜索系统

```typescript
interface GraphFilterState {
  entityTypes: string[]       // 按实体类型筛选
  timeRange?: {               // 按transaction_time范围筛选
    start: string
    end: string
  }
  searchQuery?: string        // 模糊搜索实体名
  searchResults?: string[]    // 搜索结果高亮
}

// 筛选应用
const applyFilter = (graph: Graph, filter: GraphFilterState) => {
  graph.updateData({
    nodes: allNodes
      .filter(n => filter.entityTypes.length === 0 || filter.entityTypes.includes(n.type))
      .filter(n => !filter.searchQuery || n.label.includes(filter.searchQuery))
      .map(n => ({
        ...n,
        style: {
          ...n.style,
          opacity: 1,
          // 搜索结果高亮
          halo: filter.searchResults?.includes(n.id) ? true : undefined,
          haloFill: '#ffd700'
        }
      })),
    edges: allEdges
  })
  graph.render()
}

// 搜索组件
const GraphSearchBar: React.FC = () => {
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebounce(query, 300)

  useEffect(() => {
    if (debouncedQuery.length >= 2) {
      applyFilter(graph, {
        ...currentFilter,
        searchQuery: debouncedQuery
      })
    }
  }, [debouncedQuery])

  return (
    <Input.Search
      placeholder="搜索实体名称..."
      value={query}
      onChange={e => setQuery(e.target.value)}
      allowClear
      style={{ marginBottom: 8 }}
    />
  )
}
```

### 3.4 时序可视化

```typescript
// 利用Graphiti的双时态特性展示图谱时间演变
interface TemporalViewConfig {
  validTime: string           // 有效时间（业务时间）
  transactionTime: string     // 事务时间（记录时间）
}

const TemporalGraphSlider: React.FC = () => {
  const [currentTime, setCurrentTime] = useState<Date>(new Date())
  const [isPlaying, setIsPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)

  // 按时序过滤数据：只显示valid_time ≤ currentTime的实体/关系
  const filterByTime = (time: Date) => {
    graph.updateData({
      nodes: allNodes.filter(n =>
        new Date(n.valid_time) <= time
      ),
      edges: allEdges.filter(e =>
        new Date(e.valid_time) <= time &&
        allNodes.some(n => n.id === e.source && new Date(n.valid_time) <= time) &&
        allNodes.some(n => n.id === e.target && new Date(n.valid_time) <= time)
      )
    })
    graph.render()
  }

  return (
    <div className="temporal-slider">
      <Slider
        min={timeRange.start}
        max={timeRange.end}
        value={currentTime}
        onChange={v => { setCurrentTime(v); filterByTime(v) }}
      />
      <Button icon={isPlaying ? <PauseOutlined /> : <CaretRightOutlined />}
              onClick={() => setIsPlaying(!isPlaying)} />
    </div>
  )
}
```

---

## 4. 详情面板设计

### 4.1 节点详情面板

当用户点击图谱节点时，右侧面板显示该实体的完整信息：

```typescript
interface EntityDetailPanelProps {
  entity: OntologyEntity
}

const EntityDetailPanel: React.FC<EntityDetailPanelProps> = ({ entity }) => {
  return (
    <div className="entity-detail">
      {/* 实体基本信息 */}
      <Descriptions title="基本信息" column={1}>
        <Descriptions.Item label="ID">{entity.id}</Descriptions.Item>
        <Descriptions.Item label="类型">
          <Tag color={getTypeColor(entity.type)}>{entity.type}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="名称">{entity.name}</Descriptions.Item>
        <Descriptions.Item label="valid_time">{entity.valid_time}</Descriptions.Item>
        <Descriptions.Item label="transaction_time">{entity.transaction_time}</Descriptions.Item>
      </Descriptions>

      {/* 属性列表（动态渲染） */}
      <Divider>属性</Divider>
      {Object.entries(entity.properties).map(([key, val]) => (
        <PropertyRow key={key} name={key} value={val} />
      ))}

      {/* 关联实体（可点击跳转） */}
      <Divider>关联实体</Divider>
      <RelatedEntitiesList
        entities={entity.relatedEntities}
        onEntityClick={(id) => eventBus.emit('ontology:node:select', { nodeId: id })}
      />

      {/* 操作按钮 */}
      <Space style={{ marginTop: 12 }}>
        <Button icon={<SearchOutlined />} onClick={() => focusOnGraph(entity.id)}>
          在图谱中定位
        </Button>
        <Button icon={<MessageOutlined />} onClick={() => askAbout(entity)}>
          向AI询问
        </Button>
        <Button icon={<CopyOutlined />} onClick={() => copyEntityJson(entity)}>
          复制JSON
        </Button>
      </Space>
    </div>
  )
}
```

### 4.2 关系详情面板

```typescript
const RelationshipDetailPanel: React.FC<{ edge: GraphEdge }> = ({ edge }) => {
  return (
    <div className="edge-detail">
      <Descriptions column={1}>
        <Descriptions.Item label="关系类型">
          <Tag>{edge.type}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="源实体">
          <a onClick={() => selectNode(edge.source)}>{edge.sourceName}</a>
        </Descriptions.Item>
        <Descriptions.Item label="目标实体">
          <a onClick={() => selectNode(edge.target)}>{edge.targetName}</a>
        </Descriptions.Item>
        <Descriptions.Item label="有效时间">{edge.valid_time}</Descriptions.Item>
        <Descriptions.Item label="事务时间">{edge.transaction_time}</Descriptions.Item>
      </Descriptions>
    </div>
  )
}
```

---

## 5. 与问答系统双向联动

### 5.1 问答 → 图谱

```typescript
// AI回答中的实体标记识别，点击跳转图谱并高亮
const MessageBubble = ({ content }: { content: string }) => {
  // 解析content中的实体标记: [[entity:entity_123:实体名称]]
  const parseEntityLinks = (text: string): React.ReactNode[] => {
    const regex = /\[\[entity:([^:]+):([^\]]+)\]\]/g
    const parts: React.ReactNode[] = []
    let lastIdx = 0
    let match
    while ((match = regex.exec(text)) !== null) {
      parts.push(text.slice(lastIdx, match.index))
      parts.push(
        <Tag
          key={match[1]}
          color="blue"
          style={{ cursor: 'pointer' }}
          onClick={() => {
            // 切换到图谱视图并高亮该实体
            navigateToGraphView(match![1])
          }}
        >
          {match[2]}
        </Tag>
      )
      lastIdx = regex.lastIndex
    }
    parts.push(text.slice(lastIdx))
    return parts
  }

  return <div>{parseEntityLinks(content)}</div>
}
```

### 5.2 图谱 → 问答

```typescript
// 在图谱中选中实体后可快速发起问答
const askAbout = (entity: OntologyEntity) => {
  // 预填充问题并切换到问答模式
  const prefillQuestion = `请分析「${entity.name}」(${entity.type})的详细信息，包括其属性、关联实体和可能的行动建议。`

  eventBus.emit('qa:prefill', {
    question: prefillQuestion,
    attachedEntities: [entity.id]
  })
}
```

---

## 6. 性能优化策略

| 问题 | 方案 |
|------|------|
| **大图谱渲染卡顿** | LOD分级渲染：不同缩放级别显示不同粒度；超过500节点时启用WebGL渲染 |
| **布局计算耗时** | Web Worker布局：将force/force2布局计算卸载到Worker线程 |
| **重复渲染** | 数据变更合并：100ms内的多次updateData合并为一次 |
| **内存占用高** | 虚拟画布：仅渲染视口内+缓冲区的节点；回收离屏节点实例 |

```typescript
// 大数据量下的WebGL模式切换
const initLargeGraph = (container: HTMLElement, nodeCount: number) => {
  if (nodeCount > 500) {
    return new Graph({
      container,
      renderer: 'webgl',       // WebGL渲染器
      // ...
    })
  }
  return initOntologyGraph(container)
}
```

---

## 7. 布局算法选择

| 场景 | 推荐布局 | 原因 |
|------|---------|------|
| 整体浏览 | force / force2 | 力导向自然分布，适合探索性分析 |
| 层级关系（指挥链） | dagre / compact-box | 树形层级，适合上下级关系 |
| 时序分析 | 按时间轴排列 | 展示事件先后顺序 |
| 聚类分析 | 按类型分组+子图布局 | 同类型实体聚合展示 |

---

## 8. 实施计划

| 阶段 | 内容 | 前置条件 | 预估 |
|------|------|---------|------|
| P0-1 | 节点/边视觉映射规则实现 | 已完成G6集成 | 2天 |
| P0-2 | 分层渲染(LOD) + 缩放行为 | P0-1 | 2天 |
| P0-3 | 筛选搜索+事件系统+右键菜单 | P0-1 | 2天 |
| P1-1 | 详情面板 + 与问答联动 | P0-3 | 2天 |
| P1-2 | 时序可视化滑块 | Graphiti时序数据可用 | 2天 |
| P2 | Web Worker布局 + WebGL模式 | P0-2 | 3天 |

---

*关联文档: [全链路架构设计](../../02-architecture/ARCHITECTURE_FULL_CHAIN.md), [全链路深入实现设计 v2.0](../../02-architecture/ARCHITECTURE_FULL_CHAIN.md), [ARCHITECTURE_WEB.md](../../02-architecture/ARCHITECTURE_WEB.md), [ADR-045](../../07-adr/ADR-045_frontend_visualization_g6_leaflet.md)*
