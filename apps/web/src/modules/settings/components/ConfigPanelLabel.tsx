import { Tag, Space } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { ServiceConfig } from '../types';

/** 面板标题：连接状态标签（只依赖 config，可安全内联渲染） */
export function ConfigPanelLabel({ config }: { config: ServiceConfig }) {
  const { t } = useI18n('settings');

  const statusMap: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
    connected: { color: 'success', icon: <CheckCircleOutlined />, text: t('已连接') },
    disconnected: { color: 'error', icon: <CloseCircleOutlined />, text: t('已断开') },
    not_configured: { color: 'default', icon: <MinusCircleOutlined />, text: t('未配置') },
    unknown: { color: 'warning', icon: <QuestionCircleOutlined />, text: t('未知') },
  };
  const statusInfo = statusMap[config.connection_status] || statusMap.unknown;

  return (
    <Space>
      <span style={{ fontSize: 15, fontWeight: 500 }}>{config.label}</span>
      <Tag icon={statusInfo.icon} color={statusInfo.color}>
        {statusInfo.text}
      </Tag>
      {config.last_error && <Tag color="error">{config.last_error}</Tag>}
    </Space>
  );
}
