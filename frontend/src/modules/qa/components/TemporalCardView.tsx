import React from 'react';
import { Tag, Typography, Space } from 'antd';
import { ClockCircleOutlined } from '@ant-design/icons';
import type { TemporalCard } from '../hooks/useQAI';

const { Text, Paragraph } = Typography;

export function TemporalCardView({ card }: { card: TemporalCard }) {
  return (
    <div style={{ margin: '8px 0', padding: 12, borderRadius: 8, border: '1px solid #d9d9d9', background: '#fafafa' }}>
      <Space orientation="vertical" style={{ width: '100%' }} size={4}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ClockCircleOutlined style={{ color: '#1890ff' }} />
          <Tag color="blue">{card.time_type}</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>有效时间: {card.valid_time}</Text>
        </div>
        <Paragraph style={{ margin: 0, fontSize: 13 }}>{card.answer}</Paragraph>
        {card.entity_count !== undefined && (
          <Text type="secondary" style={{ fontSize: 12 }}>相关实体: {card.entity_count}</Text>
        )}
      </Space>
    </div>
  );
}
