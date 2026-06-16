import { useState } from 'react';
import { Steps, Card, Collapse, Tag, Typography } from 'antd';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

interface PathNode {
  id: string;
  title: string;
  description?: string;
  status?: 'wait' | 'process' | 'finish' | 'error';
  detail?: Record<string, unknown>;
}

interface ReasoningPathProps {
  path: PathNode[];
  onNodeClick?: (node: PathNode) => void;
}

const STATUS_TAG_COLOR: Record<string, string> = {
  wait: 'default',
  process: 'processing',
  finish: 'green',
  error: 'red',
};

export default function ReasoningPath({ path, onNodeClick }: ReasoningPathProps) {
  const { t } = useI18n('agent');
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);

  if (!path || path.length === 0) {
    return (
      <Card title={t('reasoningChain')} size="small">
        <Text type="secondary">{t('noData')}</Text>
      </Card>
    );
  }

  const currentStep = path.findIndex((s) => s.status === 'process');
  const activeStep = currentStep !== -1 ? currentStep : path.length - 1;

  const collapseItems = path.map((node) => ({
    key: node.id,
    label: (
      <span style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }} onClick={() => onNodeClick?.(node)}>
        <Tag color={STATUS_TAG_COLOR[node.status || 'finish']}>
          {node.status || 'finish'}
        </Tag>
        <Text strong>{node.title}</Text>
      </span>
    ),
    children: (
      <div>
        {node.description && (
          <div style={{ marginBottom: 8 }}>
            <Text>{node.description}</Text>
          </div>
        )}
        {node.detail && Object.keys(node.detail).length > 0 && (
          <div>
            {Object.entries(node.detail).map(([key, value]) => (
              <div key={key} style={{ marginBottom: 4 }}>
                <Text type="secondary">{key}: </Text>
                <Text>{typeof value === 'string' ? value : JSON.stringify(value)}</Text>
              </div>
            ))}
          </div>
        )}
      </div>
    ),
  }));

  return (
    <Card title={t('reasoningChain')} size="small">
      <Steps
        orientation="vertical"
        size="small"
        current={activeStep}
        items={path.map((node) => ({
          key: node.id,
          title: (
            <span
              style={{ cursor: 'pointer' }}
              onClick={() => onNodeClick?.(node)}
            >
              {node.title}
            </span>
          ),
          description: node.description,
          status: node.status || 'finish',
        }))}
        style={{ marginBottom: 16 }}
      />
      <Collapse
        items={collapseItems}
        activeKey={expandedKeys}
        onChange={(keys) => setExpandedKeys(keys as string[])}
        size="small"
      />
    </Card>
  );
}
