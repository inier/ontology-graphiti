import { useState, useCallback } from 'react';
import { Space, Button, Divider } from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import { ConfigItemForm } from './ConfigItemForm';
import { ConnectionTestButton } from './ConnectionTestButton';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { ServiceConfig, ConfigItem, ServiceCategory } from '../types';

interface ConfigPanelBodyProps {
  config: ServiceConfig;
  onSave: (category: ServiceCategory, items: Array<{ key: string; value: string }>) => void;
  saving?: boolean;
}

/** 面板正文：持有草稿状态（每类服务一个实例，hook 调用位置固定） */
export function ConfigPanelBody({ config, onSave, saving = false }: ConfigPanelBodyProps) {
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

  const draftItems = Object.entries(formValues).map(([key, value]) => ({ key, value }));

  const handleSave = () => {
    onSave(config.category, draftItems);
  };

  const groupedItems = config.items.reduce<Record<string, ConfigItem[]>>((acc, item) => {
    const group = item.group || 'default';
    if (!acc[group]) acc[group] = [];
    acc[group].push(item);
    return acc;
  }, {});

  return (
    <>
      <div style={{ color: 'var(--odap-color-text-secondary)', marginBottom: 12 }}>
        {config.description}
      </div>
      <Form layout="vertical" size="middle">
        {Object.entries(groupedItems).map(([group, items]) => (
          <div key={group}>
            {group !== 'default' && (
              <Divider
                titlePlacement="left"
                style={{ fontSize: 13, color: 'var(--odap-color-text-tertiary)' }}
              >
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
          <Space>
            <Button type="primary" onClick={handleSave} loading={saving}>
              {t('saveButton', { label: config.label })}
            </Button>
            <ConnectionTestButton
              category={config.category}
              items={draftItems}
              onTestComplete={() => {
                /* 测试结果由 settings store 刷新，无需本地处理 */
              }}
            />
          </Space>
        </Form.Item>
      </Form>
    </>
  );
}
