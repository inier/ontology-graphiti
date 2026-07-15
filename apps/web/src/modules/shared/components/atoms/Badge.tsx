import type { FC, ReactNode, CSSProperties } from 'react';
import { Badge as AntBadge } from 'antd';

interface BadgeProps {
  count?: ReactNode;
  dot?: boolean;
  offset?: [number, number];
  overflowCount?: number;
  showZero?: boolean;
  size?: 'default' | 'small';
  status?: 'success' | 'processing' | 'error' | 'default' | 'warning';
  text?: ReactNode;
  color?: string;
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

const Badge: FC<BadgeProps> = ({
  count,
  dot,
  offset,
  overflowCount,
  showZero,
  size,
  status,
  text,
  color,
  children,
  className,
  style,
}) => {
  return (
    <AntBadge
      count={count}
      dot={dot}
      offset={offset}
      overflowCount={overflowCount}
      showZero={showZero}
      size={size}
      status={status}
      text={text}
      color={color}
      className={className}
      style={style}
    >
      {children}
    </AntBadge>
  );
};

export default Badge;
