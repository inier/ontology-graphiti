import { ProCard as Card } from '@ant-design/pro-components';
import { NODE_TYPE_LIST, type BlueprintNodeType } from './nodeTypes';

export function NodePanel() {
  const onDragStart = (event: React.DragEvent, nodeType: BlueprintNodeType) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, color: '#666', marginBottom: 8 }}>
        节点面板
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {NODE_TYPE_LIST.map(config => (
          <Card
            key={config.type}
            size="small"
            draggable
            onDragStart={e => onDragStart(e, config.type)}
            style={{
              cursor: 'grab',
              borderColor: `${config.color}44`,
              borderRadius: 6,
            }}
            styles={{ body: { padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 6 } }}
          >
            <span style={{ color: config.color, fontSize: 16, display: 'flex', alignItems: 'center' }}>
              {config.icon}
            </span>
            <span style={{ fontSize: 12, color: '#333', fontWeight: 500 }}>
              {config.label}
            </span>
          </Card>
        ))}
      </div>
    </div>
  );
}
