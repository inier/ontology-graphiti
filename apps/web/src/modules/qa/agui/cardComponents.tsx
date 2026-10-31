/**
 * AG-UI 内置卡片的本地实现（未知 / 操作 / 确认 / 输入）。
 *
 * 单独成文件的原因：`CardRegistry.tsx` 需要同时导出注册表与工厂函数，
 * 组件定义混在一起会让 react-refresh 退化为整页刷新。
 */

import React from 'react';
import { Typography } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import type { CardMetadata } from './agui_types';
import { Icon } from '@/modules/shared/components/Icon';

const { Text } = Typography;

export interface CardRendererProps {
  metadata: CardMetadata;
  onAction?: (action: string, data: unknown) => void;
  onConfirm?: (approved: boolean, editedArgs?: Record<string, unknown>) => void;
}

/**
 * 未知卡片类型的 fallback
 */
export function UnknownCard({ metadata }: CardRendererProps) {
  return (
    <Card size="small" style={{ marginTop: 8 }}>
      <Text type="secondary">未知卡片类型: {String(metadata.card_type)}</Text>
      <pre style={{ fontSize: 12, marginTop: 8, maxHeight: 120, overflow: 'auto' }}>
        {JSON.stringify(metadata.card_props, null, 2)}
      </pre>
    </Card>
  );
}

export function ActionCard({ metadata, onAction }: CardRendererProps) {
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

export function ConfirmCardUI({ metadata, onConfirm }: CardRendererProps) {
  const { question, options } = metadata.card_props as {
    question?: string;
    options?: Array<{ label: string; value: string }>;
  };
  return (
    <Card size="small" style={{ marginTop: 8, borderColor: '#faad14' }}>
      <Text strong>{question || '请确认'}</Text>
      <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
        <button onClick={() => onConfirm?.(true)}><Icon role="confirm" size={16} /> 确认</button>
        <button onClick={() => onConfirm?.(false)}><Icon role="cancel" size={16} /> 取消</button>
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

export function InputCardUI({ metadata, onConfirm }: CardRendererProps) {
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
