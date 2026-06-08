/**
 * Generative UI Card Registry
 *
 * v2.0 演示能力：7 类内置卡片类型
 * - chart / graph / temporal / report_link / action / confirm / input
 *
 * 与现有 qa/components/ 内组件复用（InlineChart / TemporalCardView / ReportLinkView）
 */

import React from 'react';
import { Card, Typography } from 'antd';
import type { CardType, CardMetadata } from './agui_types';
import { InlineChart } from '../components/InlineChart';
import { TemporalCardView } from '../components/TemporalCardView';
import { ReportLinkView } from '../components/ReportLinkView';

const { Text } = Typography;

export interface CardRendererProps {
  metadata: CardMetadata;
  onAction?: (action: string, data: unknown) => void;
  onConfirm?: (approved: boolean, editedArgs?: Record<string, unknown>) => void;
}

/**
 * 未知卡片类型的 fallback
 */
function UnknownCard({ metadata }: CardRendererProps) {
  return (
    <Card size="small" style={{ marginTop: 8 }}>
      <Text type="secondary">未知卡片类型: {String(metadata.card_type)}</Text>
      <pre style={{ fontSize: 12, marginTop: 8, maxHeight: 120, overflow: 'auto' }}>
        {JSON.stringify(metadata.card_props, null, 2)}
      </pre>
    </Card>
  );
}

function ActionCard({ metadata, onAction }: CardRendererProps) {
  const { label, action, data } = metadata.card_props as {
    label?: string;
    action?: string;
    data?: unknown;
  };
  return (
    <Card size="small" style={{ marginTop: 8 }}>
      <a
        onClick={() => onAction?.(action || 'default', data)}
        style={{ cursor: 'pointer' }}
      >
        {label || '执行操作'}
      </a>
    </Card>
  );
}

function ConfirmCardUI({ metadata, onConfirm }: CardRendererProps) {
  const { question, options } = metadata.card_props as {
    question?: string;
    options?: Array<{ label: string; value: string }>;
  };
  return (
    <Card size="small" style={{ marginTop: 8, borderColor: '#faad14' }}>
      <Text strong>{question || '请确认'}</Text>
      <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
        <button onClick={() => onConfirm?.(true)}>✓ 确认</button>
        <button onClick={() => onConfirm?.(false)}>✗ 取消</button>
      </div>
      {options && options.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {options.map((opt) => (
            <button
              key={opt.value}
              onClick={() => onConfirm?.(true, { selected: opt.value })}
              style={{ marginRight: 4 }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}

function InputCardUI({ metadata, onConfirm }: CardRendererProps) {
  const { prompt, placeholder } = metadata.card_props as {
    prompt?: string;
    placeholder?: string;
  };
  const inputRef = React.useRef<HTMLInputElement>(null);
  return (
    <Card size="small" style={{ marginTop: 8, borderColor: '#1890ff' }}>
      <Text strong>{prompt || '请输入'}</Text>
      <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
        <input
          ref={inputRef}
          placeholder={placeholder || ''}
          style={{ flex: 1, padding: '4px 8px', border: '1px solid #d9d9d9' }}
        />
        <button
          onClick={() => onConfirm?.(true, { value: inputRef.current?.value || '' })}
        >
          提交
        </button>
      </div>
    </Card>
  );
}

const REGISTRY: Record<CardType, React.FC<CardRendererProps>> = {
  chart: InlineChart as unknown as React.FC<CardRendererProps>,
  graph: UnknownCard, // G6 图谱组件占位
  temporal: TemporalCardView as unknown as React.FC<CardRendererProps>,
  report_link: ReportLinkView as unknown as React.FC<CardRendererProps>,
  action: ActionCard,
  confirm: ConfirmCardUI,
  input: InputCardUI,
};

/**
 * CardRenderer 入口：根据 card_type 选择对应组件
 */
export function CardRenderer(props: CardRendererProps) {
  const Comp = REGISTRY[props.metadata.card_type] || UnknownCard;
  return <Comp {...props} />;
}

/**
 * 列出所有已注册的卡片类型
 */
export function getRegisteredCardTypes(): CardType[] {
  return Object.keys(REGISTRY) as CardType[];
}
