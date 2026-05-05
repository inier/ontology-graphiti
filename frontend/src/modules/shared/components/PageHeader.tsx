import React from 'react';
import { Row, Col, Typography, Space, Button } from 'antd';
import type { ButtonProps } from 'antd';

const { Title } = Typography;

interface PageHeaderProps {
  title: string;
  titleLevel?: 1 | 2 | 3 | 4;
  actions?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export function PageHeader({
  title,
  titleLevel = 3,
  actions,
  className,
  style,
}: PageHeaderProps) {
  return (
    <Row
      gutter={[16, 16]}
      className={className}
      style={{
        marginBottom: 16,
        ...style,
      }}
    >
      <Col flex="1">
        <Title 
          level={titleLevel as 1 | 2 | 3 | 4} 
          style={{ 
            margin: 0, 
            textAlign: 'left' 
          }}
        >
          {title}
        </Title>
      </Col>
      <Col>
        {actions && (
          <Space>
            {actions}
          </Space>
        )}
      </Col>
    </Row>
  );
}

interface ActionButtonProps extends ButtonProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}

export function ActionButton({ icon, label, onClick, ...props }: ActionButtonProps) {
  return (
    <Button 
      icon={icon} 
      onClick={onClick} 
      {...props}
    >
      {label}
    </Button>
  );
}
