import { useCallback } from 'react';
import { Input, InputNumber, Switch, Select, Tooltip } from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import { QuestionCircleOutlined } from '@ant-design/icons';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { ConfigItem } from '../types';

interface ConfigItemFormProps {
  item: ConfigItem;
  value: string;
  onChange: (key: string, value: string) => void;
}

export function ConfigItemForm({ item, value, onChange }: ConfigItemFormProps) {
  const { t } = useI18n('settings');

  const handleChange = useCallback(
    (val: string | number | boolean | null) => {
      onChange(item.key, val == null ? '' : String(val));
    },
    [item.key, onChange],
  );

  const renderControl = () => {
    // If has choices, use Select regardless of value_type
    if (item.choices && item.choices.length > 0) {
      return (
        <Select
          value={value || undefined}
          onChange={handleChange}
          placeholder={t('placeholderSelect', { label: item.label })}
          allowClear
          options={item.choices.map((c) => ({ label: c, value: c }))}
          style={{ width: '100%' }}
        />
      );
    }

    switch (item.value_type) {
      case 'password':
        return (
          <Input.Password
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={t('placeholderInput', { label: item.label })}
            visibilityToggle
          />
        );

      case 'boolean':
        return (
          <Switch
            checked={value === 'true' || value === '1'}
            onChange={(checked) => handleChange(checked)}
          />
        );

      case 'integer':
        return (
          <InputNumber
            value={value !== '' ? Number(value) : undefined}
            onChange={(val) => handleChange(val)}
            placeholder={t('placeholderInput', { label: item.label })}
            min={item.min_val}
            max={item.max_val}
            precision={0}
            style={{ width: '100%' }}
          />
        );

      case 'float':
        return (
          <InputNumber
            value={value !== '' ? Number(value) : undefined}
            onChange={(val) => handleChange(val)}
            placeholder={t('placeholderInput', { label: item.label })}
            min={item.min_val}
            max={item.max_val}
            style={{ width: '100%' }}
          />
        );

      case 'url':
        return (
          <Input
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={t('placeholderInputUrl', { label: item.label })}
          />
        );

      case 'string':
      default:
        return (
          <Input
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={t('placeholderInput', { label: item.label })}
          />
        );
    }
  };

  return (
    <Form.Item
      label={
        <span>
          {item.label}
          {item.is_required && (
            <span style={{ color: '#ff4d4f', marginLeft: 2 }}>*</span>
          )}
          {item.description && (
            <Tooltip title={item.description}>
              <QuestionCircleOutlined
                style={{ color: '#999', marginLeft: 4, fontSize: 12 }}
              />
            </Tooltip>
          )}
        </span>
      }
      extra={
        item.has_value && item.is_sensitive
          ? t('currentConfiguredMasked')
          : undefined
      }
    >
      {renderControl()}
    </Form.Item>
  );
}
