/**
 * 三支柱状态面板 - 显示 BM25/Vector/Graph 可用性
 */
import React from 'react';
import { Card, Tag, Space, Typography, Tooltip } from 'antd';
import {
  SearchOutlined,
  ApiOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import type { PillarStatus } from '../services/nlQueryApi';

const { Text } = Typography;

const PILLAR_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  bm25: { icon: <SearchOutlined />, color: '#1890ff', label: 'BM25 关键词' },
  vector: { icon: <ApiOutlined />, color: '#52c41a', label: 'Vector 语义' },
  graph: { icon: <BranchesOutlined />, color: '#fa8c16', label: 'Graph 图推理' },
};

interface PillarStatusPanelProps {
  pillars: PillarStatus[];
  loading?: boolean;
}

export function PillarStatusPanel({ pillars, loading }: PillarStatusPanelProps) {
  return (
    <Card
      size="small"
      title="检索支柱状态"
      loading={loading}
      style={{ marginBottom: 12 }}
      styles={{ body: { padding: '8px 12px' } }}
    >
      <Space orientation="vertical" style={{ width: '100%' }} size={8}>
        {pillars.map((p) => {
          const config = PILLAR_CONFIG[p.name] || { icon: null, color: '#999', label: p.name };
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
                <span style={{ color: config.color, fontSize: 16 }}>{config.icon}</span>
                <div>
                  <Text strong style={{ fontSize: 13 }}>{config.label}</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 11 }}>{p.description}</Text>
                </div>
              </Space>
              <Tooltip title={isAvailable ? '可用' : '不可用'}>
                <Tag
                  icon={isAvailable ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                  color={isAvailable ? 'success' : 'error'}
                  style={{ margin: 0 }}
                >
                  {isAvailable ? '可用' : '离线'}
                </Tag>
              </Tooltip>
            </div>
          );
        })}
      </Space>
    </Card>
  );
}
