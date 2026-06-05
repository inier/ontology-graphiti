import type { FC, ReactNode, CSSProperties } from 'react';

interface FullScreenProps {
  header?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  headerHeight?: number;
  footerHeight?: number;
  className?: string;
  style?: CSSProperties;
}

const FullScreen: FC<FullScreenProps> = ({
  header,
  children,
  footer,
  headerHeight = 48,
  footerHeight = 48,
  className,
  style,
}) => {
  return (
    <div className={className} style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', ...style }}>
      {header && (
        <div
          style={{
            height: headerHeight,
            minHeight: headerHeight,
            display: 'flex',
            alignItems: 'center',
            padding: '0 16px',
            borderBottom: '1px solid #f0f0f0',
            flexShrink: 0,
          }}
        >
          {header}
        </div>
      )}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {children}
      </div>
      {footer && (
        <div
          style={{
            height: footerHeight,
            minHeight: footerHeight,
            display: 'flex',
            alignItems: 'center',
            padding: '0 16px',
            borderTop: '1px solid #f0f0f0',
            flexShrink: 0,
          }}
        >
          {footer}
        </div>
      )}
    </div>
  );
};

export default FullScreen;
