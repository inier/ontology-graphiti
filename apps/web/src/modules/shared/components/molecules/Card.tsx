import type { FC, ReactNode, CSSProperties } from 'react';
import { ProCard as AntCard } from '@ant-design/pro-components';

interface CardProps {
  title?: ReactNode;
  extra?: ReactNode;
  children?: ReactNode;
  bordered?: boolean;
  hoverable?: boolean;
  loading?: boolean;
  size?: 'default' | 'small';
  cover?: ReactNode;
  actions?: ReactNode[];
  className?: string;
  style?: CSSProperties;
  onClick?: (e: React.MouseEvent) => void;
}

const Card: FC<CardProps> = ({
  title,
  extra,
  children,
  bordered = true,
  hoverable = false,
  loading = false,
  size = 'default',
  cover,
  actions,
  className,
  style,
  onClick,
}) => {
  return (
    <AntCard
      title={title}
      extra={extra}
      bordered={bordered}
      hoverable={hoverable}
      loading={loading}
      size={size}
      cover={cover}
      actions={actions}
      className={className}
      style={style}
      onClick={onClick}
    >
      {children}
    </AntCard>
  );
};

export default Card;
