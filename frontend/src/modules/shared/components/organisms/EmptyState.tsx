import React from 'react';
import { Empty, Button, Typography, Space } from 'antd';
import type { ReactNode } from 'react';

const { Title, Paragraph } = Typography;

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  showSampleData?: boolean;
  onLoadSampleData?: () => void;
}

const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  showSampleData = false,
  onLoadSampleData,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px 24px',
        minHeight: 320,
      }}
    >
      <Empty
        image={icon ? undefined : Empty.PRESENTED_IMAGE_SIMPLE}
        description={null}
      >
        {icon && (
          <div style={{ fontSize: 48, color: '#bfbfbf', marginBottom: 16 }}>
            {icon}
          </div>
        )}
        <Space direction="vertical" align="center" size="small">
          <Title level={4} style={{ margin: 0, color: '#262626' }}>
            {title}
          </Title>
          {description && (
            <Paragraph
              type="secondary"
              style={{ margin: 0, maxWidth: 400, textAlign: 'center' }}
            >
              {description}
            </Paragraph>
          )}
          <Space style={{ marginTop: 16 }}>
            {actionLabel && onAction && (
              <Button type="primary" onClick={onAction}>
                {actionLabel}
              </Button>
            )}
            {showSampleData && onLoadSampleData && (
              <Button onClick={onLoadSampleData}>
                加载示例数据
              </Button>
            )}
          </Space>
        </Space>
      </Empty>
    </div>
  );
};

export default EmptyState;
