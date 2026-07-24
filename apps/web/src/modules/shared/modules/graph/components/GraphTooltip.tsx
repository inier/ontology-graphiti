import type { GraphNode, GraphEdge } from '../types';
import { useI18n } from '@/modules/shared/hooks/useI18n';

interface TooltipData {
  type: 'node' | 'edge';
  data: GraphNode | GraphEdge;
  position: { x: number; y: number };
}

interface GraphTooltipProps {
  tooltipData: TooltipData | null;
  onClose: () => void;
}

export function GraphTooltip({ tooltipData, onClose }: GraphTooltipProps) {
  const { t } = useI18n();
  if (!tooltipData) return null;

  const { type, data, position } = tooltipData;

  const renderNodeTooltip = (node: GraphNode) => (
    <div style={{
      maxWidth: '280px',
      padding: '12px',
      background: '#fff',
      borderRadius: '8px',
      boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
      border: '1px solid #e8e8e8',
      zIndex: 1000,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <div style={{
          width: '16px',
          height: '16px',
          borderRadius: '4px',
          background: node.side === 'red' ? '#f5222d' : node.side === 'blue' ? '#1890ff' : '#13c2c2',
        }} />
        <span style={{ fontSize: '14px', fontWeight: '600', color: '#333' }}>
          {node.label}
        </span>
      </div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
        <span style={{
          padding: '2px 8px',
          background: '#f5f7fa',
          borderRadius: '4px',
          fontSize: '12px',
          color: '#666',
        }}>
          ID: {node.id}
        </span>
        <span style={{
          padding: '2px 8px',
          background: '#f5f7fa',
          borderRadius: '4px',
          fontSize: '12px',
          color: '#666',
        }}>
          {t('类型')}: {node.type}
        </span>
      </div>

      {node.properties && Object.keys(node.properties).length > 0 && (
        <div>
          <div style={{ fontSize: '12px', fontWeight: '500', color: '#666', marginBottom: '6px' }}>
            {t('属性')}
          </div>
          <div style={{ maxHeight: '150px', overflowY: 'auto' }}>
            {Object.entries(node.properties).map(([key, value]) => (
              <div
                key={key}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '4px 0',
                  borderBottom: '1px solid #f5f5f5',
                  fontSize: '12px',
                }}
              >
                <span style={{ color: '#999' }}>{key}</span>
                <span style={{ color: '#333', textAlign: 'right', maxWidth: '60%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {typeof value === 'string' ? value : JSON.stringify(value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!node.properties || Object.keys(node.properties).length === 0 && (
        <div style={{ fontSize: '12px', color: '#999' }}>
          {t('暂无属性')}
        </div>
      )}
    </div>
  );

  const renderEdgeTooltip = (edge: GraphEdge) => (
    <div style={{
      maxWidth: '240px',
      padding: '12px',
      background: '#fff',
      borderRadius: '8px',
      boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
      border: '1px solid #e8e8e8',
      zIndex: 1000,
    }}>
      <div style={{ fontSize: '14px', fontWeight: '600', color: '#333', marginBottom: '8px' }}>
        {edge.label || edge.type}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <span style={{ padding: '2px 8px', background: '#f5f7fa', borderRadius: '4px', fontSize: '12px', color: '#666' }}>
          {t('类型')}: {edge.type}
        </span>
      </div>

      <div style={{ fontSize: '12px', color: '#666' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
          <span style={{ color: '#999' }}>{t('源节点')}</span>
          <span style={{ color: '#333' }}>{edge.source}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
          <span style={{ color: '#999' }}>{t('目标节点')}</span>
          <span style={{ color: '#333' }}>{edge.target}</span>
        </div>
      </div>
    </div>
  );

  return (
    <div
      style={{
        position: 'fixed',
        left: position.x + 12,
        top: position.y + 12,
        pointerEvents: 'none',
      }}
      onClick={onClose}
    >
      {type === 'node' ? renderNodeTooltip(data as GraphNode) : renderEdgeTooltip(data as GraphEdge)}
    </div>
  );
}
