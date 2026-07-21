import { useState, useCallback } from 'react';
import { Collapse, Tag, Space, Button, Divider } from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons';
import { ConfigItemForm } from './ConfigItemForm';
import { ConnectionTestButton } from './ConnectionTestButton';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { ServiceConfig, ConfigItem } from '../types';

interface ConfigGroupProps {
  config: ServiceConfig;
  onSave: (category: string, items: Array<{ key: string; value: string }>) => void;
  saving?: boolean;
}

export function ConfigGroup({ config, onSave, saving = false }: ConfigGroupProps) {
  const { t } = useI18n('settings');

  const [formValues, setFormValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    config.items.forEach((item: ConfigItem) => {
      initial[item.key] = item.display_value ?? '';
    });
    return initial;
  });

  const handleChange = useCallback((key: string, value: string) => {
    setFormValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSave = () => {
    const items = Object.entries(formValues).map(([key, value]) => ({
      key,
      value,
    }));
    onSave(config.category, items);
  };

  const handleTestComplete = () => {
    // After test, refresh is handled by the store
  };

  const CONNECTION_STATUS_MAP: Record<
    string,
    { color: string; icon: React.ReactNode; text: string }
  > = {
    connected: {
      color: 'success',
      icon: <CheckCircleOutlined />,
      text: t('已连接'),
    },
    disconnected: {
      color: 'error',
      icon: <CloseCircleOutlined />,
      text: t('已断开'),
    },
    not_configured: {
      color: 'default',
      icon: <MinusCircleOutlined />,
      text: t('未配置'),
    },
    unknown: {
      color: 'warning',
      icon: <QuestionCircleOutlined />,
      text: t('未知'),
    },
  };

  const statusInfo = CONNECTION_STATUS_MAP[config.connection_status] || CONNECTION_STATUS_MAP.unknown;

  // Group items by their group field
  const groupedItems = config.items.reduce<
    Record<string, ConfigItem[]>
  >((acc, item) => {
    const group = item.group || 'default';
    if (!acc[group]) acc[group] = [];
    acc[group].push(item);
    return acc;
  }, {});

  const panelHeader = (
    <Space>
      <span style={{ fontSize: 15, fontWeight: 500 }}>{config.label}</span>
      <Tag icon={statusInfo.icon} color={statusInfo.color}>
        {statusInfo.text}
      </Tag>
      {config.last_error && (
        <Tag color="error">{config.last_error}</Tag>
      )}
    </Space>
  );

  return {
    key: config.category,
    label: panelHeader,
    extra: (
      <Space onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <ConnectionTestButton
          category={config.category}
          items={Object.entries(formValues).map(([key, value]) => ({
            key,
            value,
          }))}
          onTestComplete={handleTestComplete}
        />
      </Space>
    ),
    children: (
      <>
        <div style={{ color: '#666', marginBottom: 12 }}>{config.description}</div>
        <Form layout="vertical" size="middle">
          {Object.entries(groupedItems).map(([group, items]) => (
            <div key={group}>
              {group !== 'default' && (
                <Divider orientation="left" style={{ fontSize: 13, color: '#888' }}>
                  {group}
                </Divider>
              )}
              {items
                .sort((a, b) => a.sort_order - b.sort_order)
                .map((item) => (
                  <ConfigItemForm
                    key={item.key}
                    item={item}
                    value={formValues[item.key] ?? ''}
                    onChange={handleChange}
                  />
                ))}
            </div>
          ))}
          <Divider />
          <Form.Item>
            <Button type="primary" onClick={handleSave} loading={saving}>
              {t('saveButton', { label: config.label })}
            </Button>
          </Form.Item>
        </Form>
      </>
    ),
  };
}
