# Contract: Generative UI 卡片注册契约（AG-UI TOOL_CALL_RESULT 版）

**Date**: 2026-06-08 (FINAL)
**Status**: 草案 v1.0
**依赖**: [ag-ui-bridge.md §3.1 #4](./ag-ui-bridge.md) · [data-model.md](../data-model.md) · [hitl-flow.md §5](./hitl-flow.md) · [AG-UI Events 官方文档](https://docs.ag-ui.com/concepts/events)
**取代**: 原 [generative-ui-card.md v0.1](./generative-ui-card.md)（OAUIP 自研版，已废止）

---

## 1. 概述

Generative UI 卡片是 **AG-UI `TOOL_CALL_RESULT` 事件**的客户端渲染机制 —— 后端将工具调用的输出以 **JSON 描述**形式推送到 `TOOL_CALL_RESULT.content`，前端查表找到对应 React 组件渲染。

**与 OAUIP 自研版的根本差异**：

| 维度 | OAUIP 自研版 | AG-UI 版 |
|------|-------------|---------|
| 事件类型 | 自研 `oauip.card` | AG-UI 标准 `TOOL_CALL_RESULT` |
| 协议兼容性 | ODAP 独家 | 6+ 大厂通用 |
| 卡片载荷位置 | `card_type` + `card_props` 在事件顶层 | `content: '{"card_type": ..., "card_props": ...}'` 字符串内 |
| 配套事件 | `oauip.action` | AG-UI `resume[]` 机制（同一套） |
| 集成复杂度 | 高（自研事件类型） | 低（标准事件） |

**核心原则**：
- 卡片是**纯函数组件**（props 决定渲染）
- 注册表在启动时静态注册 + 运行时动态注入
- TypeScript 类型系统保证 `card_props` 类型安全
- **降级策略**：未注册的 `card_type` 渲染占位 Alert，**不报错**

---

## 2. 卡片接口

```typescript
// frontend/src/modules/qa/cards/types.ts

import { type ReactNode } from 'react';

/** 卡片渲染器接口 */
export interface CardRenderer<TProps = Record<string, any>> {
  /** 卡片类型，必须与后端 TOOL_CALL_RESULT.content.card_type 对应 */
  card_type: string;

  /** 卡片组件（纯函数） */
  component: React.ComponentType<TProps>;

  /** Props 校验（可选，运行时校验） */
  propSchema?: import('zod').ZodType<TProps>;

  /** 卡片版本（用于未来迁移） */
  version: string;
}

/** 卡片 props 通用字段 */
export interface BaseCardProps {
  /** 卡片唯一 ID（前端生成） */
  card_id: string;

  /** 关联的 AG-UI toolCallId */
  tool_call_id: string;

  /** 关联的 threadId（AG-UI 规定） */
  thread_id: string;

  /** 关联的 runId（用于 resume 关联） */
  run_id?: string;

  /** HITL 中断 ID（仅 HITL 卡片有） */
  interrupt_id?: string;

  /** AG-UI Interrupt.expiresAt（仅 HITL 卡片有） */
  expires_at?: string;
}

/** AG-UI TOOL_CALL_RESULT.content 解析后的结构 */
export interface AGUIToolCallResultContent {
  card_type: string;
  card_props: Record<string, any>;
  /** 可选：HITL 关联（仅 ask_user_question 工具） */
  hitl?: {
    interrupt_id: string;
    reason: 'confirmation' | 'input_required' | 'tool_call';
    response_schema: Record<string, any>;
    expires_at?: string;
  };
}

// === 各类型卡片 props ===

/** ChartCard — 升级自 InlineChart */
export interface ChartCardProps extends BaseCardProps {
  chart_type: 'line' | 'bar' | 'pie' | 'scatter';
  data: any[];
  title?: string;
  x_field?: string;
  y_field?: string;
}

/** GraphCard — G6 图谱缩略图 */
export interface GraphCardProps extends BaseCardProps {
  nodes: Array<{ id: string; label: string; type?: string }>;
  edges: Array<{ source: string; target: string; label?: string }>;
  layout?: 'force' | 'circular' | 'dagre';
  highlight_node_ids?: string[];
}

/** TemporalCard — 时间线视图 */
export interface TemporalCardProps extends BaseCardProps {
  start: string;
  end: string;
  events: Array<{ at: string; title: string; description?: string }>;
}

/** ReportLinkCard — 报告链接 */
export interface ReportLinkCardProps extends BaseCardProps {
  report_id: string;
  report_title: string;
  url: string;
  preview?: string;
}

/** ActionCard — HITL 工具调用审批 */
export interface ActionCardProps extends BaseCardProps {
  action_type: 'create' | 'update' | 'delete' | 'execute';
  target_resource: { type: string; id: string; name: string };
  diff?: Record<string, { before: any; after: any }>;
}

/** ConfirmCard — HITL 二元确认 */
export interface ConfirmCardProps extends BaseCardProps {
  question: string;
  default_choice?: 'yes' | 'no';
  warning?: string;
}

/** InputCard — HITL 结构化输入 */
export interface InputCardProps extends BaseCardProps {
  question: string;
  input_type: 'text' | 'number' | 'select' | 'multiselect';
  options?: Array<{ value: string; label: string }>;
  required: boolean;
  default_value?: any;
}
```

---

## 3. 注册表

```typescript
// frontend/src/modules/qa/cards/registry.ts

import type { CardRenderer } from './types';
import { ChartCard } from './ChartCard';
import { GraphCard } from './GraphCard';
import { TemporalCard } from './TemporalCard';
import { ReportLinkCard } from './ReportLinkCard';
import { ActionCard } from './ActionCard';
import { ConfirmCard } from './ConfirmCard';
import { InputCard } from './InputCard';

/** 卡片注册表（静态 + 运行时注入） */
const registry = new Map<string, CardRenderer>();

/** 注册卡片 */
export function registerCard<TProps>(renderer: CardRenderer<TProps>): void {
  if (registry.has(renderer.card_type)) {
    console.warn(`Card type "${renderer.card_type}" is being re-registered.`);
  }
  registry.set(renderer.card_type, renderer as CardRenderer);
}

/** 获取卡片渲染器 */
export function getCardRenderer(card_type: string): CardRenderer | undefined {
  return registry.get(card_type);
}

/** 列出所有已注册卡片 */
export function listRegisteredCards(): string[] {
  return Array.from(registry.keys());
}

/** 启动时静态注册（7 类内置卡片） */
export function initCardRegistry(): void {
  registerCard({ card_type: 'chart', component: ChartCard, version: '1.0' });
  registerCard({ card_type: 'graph', component: GraphCard, version: '1.0' });
  registerCard({ card_type: 'temporal', component: TemporalCard, version: '1.0' });
  registerCard({ card_type: 'report_link', component: ReportLinkCard, version: '1.0' });
  registerCard({ card_type: 'action', component: ActionCard, version: '1.0' });
  registerCard({ card_type: 'confirm', component: ConfirmCard, version: '1.0' });
  registerCard({ card_type: 'input', component: InputCard, version: '1.0' });
}
```

---

## 4. 渲染入口

```typescript
// frontend/src/modules/qa/components/GenerativeMessageBubble.tsx

import { Alert, Space } from 'antd';
import { getCardRenderer } from '../cards/registry';
import type { AGUIToolCallResultContent } from '../cards/types';
import type { AGUIToolCallResultEvent, AGUIRunFinishedEvent } from '../types/agui';

interface Props {
  /** AG-UI TOOL_CALL_RESULT 事件 */
  resultEvent: AGUIToolCallResultEvent;

  /** 关联的 Interrupt 事件（仅 HITL） */
  interruptEvent?: AGUIRunFinishedEvent['outcome']['interrupts'][0];

  /** 用户操作回调（用于 HITL 卡片发送 resume） */
  onResume: (interruptId: string, payload: any) => void;

  /** 用户操作回调（用于普通 Action 卡片） */
  onAction?: (action: { type: string; payload: any }) => void;
}

export function GenerativeMessageBubble({
  resultEvent,
  interruptEvent,
  onResume,
  onAction,
}: Props) {
  // 1. 解析 TOOL_CALL_RESULT.content（必为 JSON 字符串）
  let parsed: AGUIToolCallResultContent;
  try {
    parsed = JSON.parse(resultEvent.content);
  } catch (e) {
    return (
      <Alert
        type="error"
        message="TOOL_CALL_RESULT.content 不是合法 JSON"
        description={resultEvent.content}
      />
    );
  }

  // 2. 查找卡片渲染器
  const renderer = getCardRenderer(parsed.card_type);

  if (!renderer) {
    // 未知卡片类型：渲染占位 + 静默降级
    return (
      <div className="card-placeholder">
        <Alert
          type="warning"
          message={`未知卡片类型: ${parsed.card_type}`}
          description="前端未注册此卡片，将以纯文本显示"
        />
        <pre>{JSON.stringify(parsed.card_props, null, 2)}</pre>
      </div>
    );
  }

  // 3. 合并 props（基础 + 卡片特定）
  const Component = renderer.component;
  const props = {
    ...parsed.card_props,
    card_id: `${resultEvent.toolCallId}-${resultEvent.messageId}`,
    tool_call_id: resultEvent.toolCallId,
    thread_id: '',  // 由 AGUIProvider 注入
    interrupt_id: interruptEvent?.id,
    expires_at: interruptEvent?.expiresAt,
    onAction: interruptEvent
      ? (action: any) => onResume(interruptEvent.id, action)
      : onAction,
  };

  return <Component {...props} />;
}
```

---

## 5. 内置卡片实现示例

### 5.1 ChartCard（升级自 InlineChart）

```typescript
// frontend/src/modules/qa/cards/ChartCard.tsx

import ReactECharts from 'echarts-for-react';
import type { ChartCardProps } from './types';

export function ChartCard({
  chart_type, data, title, x_field, y_field,
  onAction,
}: ChartCardProps) {
  const option = buildEChartsOption(chart_type, data, x_field, y_field, title);

  return (
    <div className="chart-card">
      {title && <h4>{title}</h4>}
      <ReactECharts option={option} style={{ height: 300 }} />
    </div>
  );
}

function buildEChartsOption(type, data, xField, yField, title) {
  return {
    title: title ? { text: title } : undefined,
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.map(d => d[xField]) },
    yAxis: { type: 'value' },
    series: [{ type, data: data.map(d => d[yField]) }],
  };
}
```

### 5.2 GraphCard（新增）

```typescript
// frontend/src/modules/qa/cards/GraphCard.tsx

import { Graph } from '@antv/g6';
import { useEffect, useRef } from 'react';
import type { GraphCardProps } from './types';

export function GraphCard({
  nodes, edges, layout, highlight_node_ids,
}: GraphCardProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const graph = new Graph({
      container: containerRef.current!,
      data: { nodes, edges },
      layout: { type: layout ?? 'force' },
      node: {
        style: {
          fill: (d: any) => highlight_node_ids?.includes(d.id) ? '#1677ff' : '#ccc',
        },
      },
    });
    graph.render();
    return () => graph.destroy();
  }, [nodes, edges, layout, highlight_node_ids]);

  return (
    <div className="graph-card">
      <div ref={containerRef} style={{ width: '100%', height: 300 }} />
    </div>
  );
}
```

### 5.3 ConfirmCard（HITL 确认）

```typescript
// frontend/src/modules/qa/cards/ConfirmCard.tsx

import { Button, Space, Alert } from 'antd';
import type { ConfirmCardProps } from './types';

export function ConfirmCard({
  question, warning, onAction,
}: ConfirmCardProps) {
  // 渲染 yes/no 两个按钮
  return (
    <div className="confirm-card">
      {warning && <Alert type="warning" message={warning} />}
      <p>{question}</p>
      <Space>
        <Button
          type="primary"
          onClick={() => onAction({ approved: true })}
        >
          确认
        </Button>
        <Button
          onClick={() => onAction({ approved: false })}
        >
          取消
        </Button>
      </Space>
    </div>
  );
}
```

### 5.4 InputCard（HITL 输入）

```typescript
// frontend/src/modules/qa/cards/InputCard.tsx

import { useState } from 'react';
import { Button, Input, Select, Space, Alert } from 'antd';
import type { InputCardProps } from './types';

export function InputCard({
  question, input_type, options, required, default_value,
  onAction,
}: InputCardProps) {
  const [value, setValue] = useState(default_value);

  const renderInput = () => {
    switch (input_type) {
      case 'text':
        return <Input value={value} onChange={e => setValue(e.target.value)} />;
      case 'number':
        return <Input type="number" value={value} onChange={e => setValue(e.target.value)} />;
      case 'select':
        return (
          <Select
            value={value}
            onChange={setValue}
            options={options}
            style={{ minWidth: 200 }}
          />
        );
      case 'multiselect':
        return (
          <Select
            mode="multiple"
            value={value || []}
            onChange={setValue}
            options={options}
            style={{ minWidth: 200 }}
          />
        );
    }
  };

  return (
    <div className="input-card">
      <p>{question}</p>
      {renderInput()}
      <Space>
        <Button
          type="primary"
          disabled={required && !value}
          onClick={() => onAction({ value })}
        >
          提交
        </Button>
      </Space>
    </div>
  );
}
```

---

## 6. AG-UI 事件 → 卡片 props 映射

后端 OpenHarness 工具的输出格式约定（**这是协议契约**）：

| 工具 | 输出 JSON 结构 | card_type | 关键 props |
|------|--------------|-----------|-----------|
| `chart_query` | `{"card_type": "chart", "card_props": {chart_type, data, ...}}` | `chart` | `chart_type`, `data`, `x_field`, `y_field` |
| `graph_query` | `{"card_type": "graph", "card_props": {nodes, edges, ...}}` | `graph` | `nodes`, `edges`, `layout` |
| `temporal_query` | `{"card_type": "temporal", "card_props": {start, end, events}}` | `temporal` | `start`, `end`, `events` |
| `report_link` | `{"card_type": "report_link", "card_props": {report_id, ...}}` | `report_link` | `report_id`, `url` |
| `permission_request` | `{"card_type": "action", "card_props": {action_type, ...}, "hitl": {...}}` | `action` | `action_type`, `target_resource` |
| `ask_user_question` | **不走 TOOL_CALL_RESULT**，走 `RUN_FINISHED.interrupts[]` | `confirm` / `input` | 取决于 `input_type` |

**关键约定**：
- 工具输出**必须是合法 JSON 字符串**（不是 Python dict）
- `card_type` 与前端注册表一一对应
- 复杂字段（`data`, `nodes`, `edges`）是数组
- HITL 工具（`ask_user_question`, `permission_request`）的输出在**Bridge 层**被拦截，**不**进入 `TOOL_CALL_RESULT`，而是触发 `RUN_FINISHED.interrupts[]`

---

## 7. HITL 卡片特殊处理

`ask_user_question` 和 `permission_request` 的输出**不**通过 `TOOL_CALL_RESULT` 传递，而是通过 `RUN_FINISHED.outcome.interrupts[]` 携带：

```typescript
// frontend/src/modules/qa/components/HITLPanel.tsx

import { Card, Space, Tag } from 'antd';
import { getCardRenderer } from '../cards/registry';
import type { Interrupt } from '../types/agui';

interface Props {
  interrupt: Interrupt;
  threadId: string;
  runId: string;
  onResume: (interruptId: string, status: 'resolved' | 'cancelled', payload: any) => void;
}

export function HITLPanel({ interrupt, threadId, runId, onResume }: Props) {
  // 从 interrupt.metadata.card_type 决定渲染哪类卡片
  const cardType = interrupt.metadata?.card_type || inferCardType(interrupt.reason);
  const renderer = getCardRenderer(cardType);

  if (!renderer) {
    return (
      <Card>
        <Tag color="blue">{interrupt.reason}</Tag>
        <p>{interrupt.message}</p>
        <p>未知卡片类型: {cardType}</p>
      </Card>
    );
  }

  const Component = renderer.component;
  return (
    <Component
      {...interrupt.metadata}
      card_id={`hitl-${interrupt.id}`}
      tool_call_id={interrupt.toolCallId || ''}
      thread_id={threadId}
      run_id={runId}
      interrupt_id={interrupt.id}
      expires_at={interrupt.expiresAt}
      onAction={(payload: any) => onResume(interrupt.id, 'resolved', payload)}
    />
  );
}

function inferCardType(reason: string): string {
  switch (reason) {
    case 'confirmation': return 'confirm';
    case 'input_required': return 'input';
    case 'tool_call': return 'action';
    default: return 'action';
  }
}
```

---

## 8. 卡片测试

```typescript
// tests/unit/test_card_registry.ts

import { describe, it, expect, beforeEach } from 'vitest';
import { registerCard, getCardRenderer, listRegisteredCards, initCardRegistry } from '@modules/qa/cards/registry';
import { ChartCard } from '@modules/qa/cards/ChartCard';

describe('CardRegistry', () => {
  beforeEach(() => {
    listRegisteredCards().forEach(t => {
      // 简单测试不 mock 整个 registry，只验证关键行为
    });
  });

  it('registers and retrieves a card', () => {
    registerCard({ card_type: 'test', component: ChartCard, version: '1.0' });
    expect(getCardRenderer('test')).toBeDefined();
    expect(getCardRenderer('test')!.component).toBe(ChartCard);
  });

  it('returns undefined for unregistered card', () => {
    expect(getCardRenderer('nonexistent')).toBeUndefined();
  });

  it('initCardRegistry registers all 7 built-in cards', () => {
    initCardRegistry();
    const cards = listRegisteredCards();
    expect(cards).toHaveLength(7);
    expect(cards).toContain('chart');
    expect(cards).toContain('graph');
    expect(cards).toContain('temporal');
    expect(cards).toContain('report_link');
    expect(cards).toContain('action');
    expect(cards).toContain('confirm');
    expect(cards).toContain('input');
  });
});

describe('GenerativeMessageBubble', () => {
  it('parses TOOL_CALL_RESULT.content as JSON', () => {
    const resultEvent = {
      type: 'TOOL_CALL_RESULT',
      messageId: 'msg_1',
      toolCallId: 'tc-1',
      content: JSON.stringify({ card_type: 'chart', card_props: { data: [1, 2, 3] } }),
      role: 'tool' as const,
    };
    // 渲染测试
  });

  it('shows fallback for unknown card_type', () => {
    const resultEvent = {
      type: 'TOOL_CALL_RESULT',
      messageId: 'msg_1',
      toolCallId: 'tc-1',
      content: JSON.stringify({ card_type: 'unknown', card_props: {} }),
      role: 'tool' as const,
    };
    // 验证渲染 Alert
  });

  it('shows error for invalid JSON content', () => {
    const resultEvent = {
      type: 'TOOL_CALL_RESULT',
      messageId: 'msg_1',
      toolCallId: 'tc-1',
      content: 'not valid JSON',
      role: 'tool' as const,
    };
    // 验证渲染错误 Alert
  });
});
```

---

## 9. 动态注入（MVP 不实现，留口）

业务方可通过 `registerCard()` 在运行时注入新卡片类型：

```typescript
// 业务模块初始化时
import { registerCard } from '@modules/qa/cards/registry';
import { MyCustomCard } from './MyCustomCard';

registerCard({
  card_type: 'military_asset_summary',
  component: MyCustomCard,
  version: '1.0',
});
```

**注意事项**：
- 动态注入的卡片必须有版本号，便于协议升级时替换
- 后端推送的 `card_props` 必须能被动态注入的 `propSchema` 校验通过

---

## 10. 卡片版本管理

**场景**：协议升级时，后端推送新版本 `card_type='chart' v0.2`，但前端只注册了 `v0.1`。

**策略**：
- 卡片注册表的 `version` 字段用于未来版本协商
- 当前 MVP：忽略 `version`，直接用最新注册的渲染器
- Phase 4 升级：前端检测 `card_props` 中的 `__version` 字段，若不兼容则降级到默认渲染

---

## 11. 关联文档

- [ag-ui-bridge.md §3.1 #4](./ag-ui-bridge.md) — `ToolExecutionCompleted` → `TOOL_CALL_RESULT` 翻译
- [hitl-flow.md §5](./hitl-flow.md) — 工具 schema → responseSchema 派生 → 卡片映射
- [data-model.md](../data-model.md) — 工具输出无服务端持久化
- [AG-UI Tool Call Events](https://docs.ag-ui.com/concepts/events#tool-call-events) — `TOOL_CALL_RESULT` 字段定义
- [plan.md Phase 3 F-04](../plan.md) — 前端卡片实现任务

---

**Version**: 1.0 (FINAL) | **Date**: 2026-06-08
