import type { FC, CSSProperties } from 'react';
import * as Icons from '@ant-design/icons';

interface IconProps {
  name: string;
  size?: number;
  color?: string;
  className?: string;
  style?: CSSProperties;
  onClick?: (e: React.MouseEvent) => void;
}

const Icon: FC<IconProps> = ({ name, size, color, className, style, onClick }) => {
  const IconsRecord: Record<string, FC<{ className?: string; style?: CSSProperties; onClick?: (e: React.MouseEvent) => void }>> = Icons as unknown as Record<string, FC<{ className?: string; style?: CSSProperties; onClick?: (e: React.MouseEvent) => void }>>;
  const AntIcon = IconsRecord[name];

  if (!AntIcon) {
    return null;
  }

  const mergedStyle: CSSProperties = {
    ...style,
    ...(size ? { fontSize: size } : {}),
    ...(color ? { color } : {}),
  };

  return <AntIcon className={className} style={mergedStyle} onClick={onClick} />;
};

export default Icon;
