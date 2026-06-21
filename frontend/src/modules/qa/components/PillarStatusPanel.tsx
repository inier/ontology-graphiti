/**
 * 三支柱状态面板 - 显示 BM25/Vector/Graph 可用性
 */
import React from 'react';
import { Tag, Space, Typography, Tooltip } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import {
  SearchOutlined,
  ApiOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import type { PillarStatus } from '../services/nlQueryApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

interface PillarStatusPanelProps {
  pillars: PillarStatus[];
  loading?: boolean;
}

const PILLAR_COLOR: Record<string, string> = {
  bm25: '#1890ff',
  vector: '#52c41a',
  graph: '#fa8c16',
};

const PILLAR_ICON: Record<string, React.ReactNode> = {
  bm25: <SearchOutlined />,
  vector: <ApiOutlined />,
  graph: <BranchesOutlined />,
};

export function PillarStatusPanel({ pillars, loading }: PillarStatusPanelProps) {
  const { t } = useI18n('qa');

  return (
    <Card
      size="small"
      title={t('pillar.title')}
      loading={loading}
      style={{ marginBottom: 12 }}
      styles={{ body: { padding: '8px 12px' } }}
    >
      <Space orientation="vertical" style={{ width: '100%' }} size={8}>
        {pillars.map((p) => {
          const isAvailable = p.status === 'available';
          return (
            <div
              key={p.name}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '4px 8px',
                borderRadius: 6,
                background: isAvailable ? '#f6ffed' : '#fff2f0',
              }}
            >
              <Space size={8}>
                <span style={{ color: PILLAR_COLOR[p.name] || '#999', fontSize: 16 }}>
                  {PILLAR_ICON[p.name] || null}
                </span>
                <div>
                  <Text strong style={{ fontSize: 13 }}>
                    {p.name === 'bm25' ? t('pillar.bm25') : p.name === 'vector' ? t('pillar.vector') : t('pillar.graph')}
                  </Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 11 }}>{p.description}</Text>
                </div>
              </Space>
              <Tooltip title={isAvailable ? t('pillar.available') : t('pillar.unavailable')}>
                <Tag
                  icon={isAvailable ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                  color={isAvailable ? 'success' : 'error'}
                  style={{ margin: 0 }}
                >
                  {isAvailable ? t('pillar.available') : t('pillar.offline')}
                </Tag>
              </Tooltip>
            </div>
          );
        })}
      </Space>
    </Card>
  );
}
