import type { FC, ReactNode, CSSProperties } from 'react';

interface MasterDetailProps {
  master: ReactNode;
  detail: ReactNode;
  masterWidth?: number | string;
  detailMinWidth?: number;
  selectedId?: string;
  emptyText?: string;
  className?: string;
  style?: CSSProperties;
}

const MasterDetail: FC<MasterDetailProps> = ({
  master,
  detail,
  masterWidth = 320,
  detailMinWidth = 400,
  selectedId,
  emptyText = 'Select an item to view details',
  className,
  style,
}) => {
  return (
    <div className={className} style={{ display: 'flex', height: '100%', ...style }}>
      <div
        style={{
          width: masterWidth,
          minWidth: masterWidth,
          borderRight: '1px solid #f0f0f0',
          overflow: 'auto',
        }}
      >
        {master}
      </div>
      <div style={{ flex: 1, minWidth: detailMinWidth, overflow: 'auto' }}>
        {selectedId ? detail : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#999' }}>
            {emptyText}
          </div>
        )}
      </div>
    </div>
  );
};

export default MasterDetail;
