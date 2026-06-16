import { Button, Space, Tooltip, Dropdown } from 'antd';
import {
  SaveOutlined,
  CheckCircleOutlined,
  RocketOutlined,
  LayoutOutlined,
  ExportOutlined,
  DeleteOutlined,
} from '@ant-design/icons';

interface BlueprintToolbarProps {
  onSave: () => void;
  onValidate: () => void;
  onPublish: () => void;
  onAutoLayout: () => void;
  onDeleteSelected?: () => void;
  onExport?: (format: 'json' | 'code') => void;
  hasBlueprint: boolean;
}

export function BlueprintToolbar({
  onSave,
  onValidate,
  onPublish,
  onAutoLayout,
  onDeleteSelected,
  onExport,
  hasBlueprint,
}: BlueprintToolbarProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 16px',
        borderBottom: '1px solid #f0f0f0',
        background: '#fafafa',
      }}
    >
      <Space>
        <Tooltip title="保存">
          <Button icon={<SaveOutlined />} onClick={onSave} disabled={!hasBlueprint}>
            保存
          </Button>
        </Tooltip>
        <Tooltip title="验证">
          <Button icon={<CheckCircleOutlined />} onClick={onValidate} disabled={!hasBlueprint}>
            验证
          </Button>
        </Tooltip>
        <Tooltip title="发布">
          <Button icon={<RocketOutlined />} onClick={onPublish} disabled={!hasBlueprint} data-tour="blueprint-run-btn">
            发布
          </Button>
        </Tooltip>
        <Tooltip title="自动布局">
          <Button icon={<LayoutOutlined />} onClick={onAutoLayout} disabled={!hasBlueprint}>
            自动布局
          </Button>
        </Tooltip>
        <Dropdown
          menu={{
            items: [
              { key: 'json', label: '导出 JSON', onClick: () => onExport?.('json') },
              { key: 'code', label: '导出代码', onClick: () => onExport?.('code') },
            ],
          }}
        >
          <Button icon={<ExportOutlined />} disabled={!hasBlueprint}>
            导出
          </Button>
        </Dropdown>
      </Space>
      {onDeleteSelected && (
        <Button danger icon={<DeleteOutlined />} onClick={onDeleteSelected}>
          删除选中
        </Button>
      )}
    </div>
  );
}
