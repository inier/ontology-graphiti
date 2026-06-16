import { Button, Tooltip } from 'antd';
import { ZoomInOutlined, ZoomOutOutlined, ExpandOutlined, AimOutlined } from '@ant-design/icons';
import { ZOOM_MIN, ZOOM_MAX } from '../utils/graphStyles';

interface GraphControlsProps {
  zoomLevel: number;
  minimapOpen: boolean;
  onCenterView: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onZoomReset: () => void;
  onToggleMinimap: () => void;
}

export function GraphControls({
  zoomLevel,
  minimapOpen,
  onCenterView,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  onToggleMinimap,
}: GraphControlsProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 0,
        background: 'rgba(255,255,255,0.72)',
        backdropFilter: 'blur(6px)',
        borderRadius: minimapOpen ? '0 8px 8px 0' : 8,
        padding: '3px 2px',
        boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
        userSelect: 'none',
      }}
    >
      <Tooltip title="一键居中（保持缩放）" placement="left">
        <Button
          type="text"
          size="small"
          icon={<AimOutlined />}
          onClick={onCenterView}
        />
      </Tooltip>

      <Tooltip title="放大" placement="left">
        <Button
          type="text"
          size="small"
          icon={<ZoomInOutlined />}
          onClick={onZoomIn}
          disabled={zoomLevel >= ZOOM_MAX}
          style={zoomLevel > 1.01 ? { color: '#1890ff', fontWeight: 'bold' } : undefined}
        />
      </Tooltip>

      <Tooltip title="点击重置为100%" placement="left">
        <div
          onClick={onZoomReset}
          style={{
            textAlign: 'center',
            fontSize: 11,
            color: zoomLevel > 1.01 ? '#1890ff' : zoomLevel < 0.99 ? '#fa8c16' : '#666',
            padding: '1px 3px',
            minWidth: 40,
            fontWeight: Math.abs(zoomLevel - 1) > 0.01 ? 700 : 500,
            borderTop: '1px solid #f0f0f0',
            borderBottom: '1px solid #f0f0f0',
            cursor: 'pointer',
            userSelect: 'none',
          }}
        >
          {Math.round(zoomLevel * 100)}%
        </div>
      </Tooltip>

      <Tooltip title="缩小" placement="left">
        <Button
          type="text"
          size="small"
          icon={<ZoomOutOutlined />}
          onClick={onZoomOut}
          disabled={zoomLevel <= ZOOM_MIN}
          style={zoomLevel < 0.99 ? { color: '#fa8c16', fontWeight: 'bold' } : undefined}
        />
      </Tooltip>

      <Tooltip title="全局缩略图" placement="left">
        <Button
          type={minimapOpen ? 'primary' : 'text'}
          size="small"
          icon={<ExpandOutlined />}
          onClick={onToggleMinimap}
        />
      </Tooltip>
    </div>
  );
}
