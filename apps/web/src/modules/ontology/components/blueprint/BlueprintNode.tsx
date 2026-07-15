import type { NodeProps } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';
import { NODE_TYPE_CONFIG, type BlueprintNodeType } from './nodeTypes';

interface BlueprintNodeData {
  label: string;
  nodeType: BlueprintNodeType;
  config?: Record<string, unknown>;
  [key: string]: unknown;
}

export function BlueprintNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as BlueprintNodeData;
  const config = NODE_TYPE_CONFIG[nodeData.nodeType];

  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 8,
        border: `2px solid ${selected ? config?.color || '#1890ff' : '#e8e8e8'}`,
        boxShadow: selected ? `0 0 0 2px ${config?.color || '#1890ff'}33` : '0 2px 8px rgba(0,0,0,0.08)',
        minWidth: 160,
        fontSize: 13,
        overflow: 'hidden',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: config?.color || '#1890ff', width: 8, height: 8 }} />
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          background: `${config?.color || '#1890ff'}11`,
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <span style={{ color: config?.color || '#1890ff', fontSize: 16, display: 'flex', alignItems: 'center' }}>
          {config?.icon}
        </span>
        <span style={{ color: config?.color || '#1890ff', fontWeight: 600, fontSize: 12 }}>
          {config?.label || nodeData.nodeType}
        </span>
      </div>
      <div style={{ padding: '8px 12px', color: '#333', fontWeight: 500 }}>
        {nodeData.label}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: config?.color || '#1890ff', width: 8, height: 8 }} />
    </div>
  );
}
