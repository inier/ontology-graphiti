import { useCallback } from 'react';
import { Input, InputNumber, Switch, Select, Form, Tooltip } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';
import type { ConfigItem } from '../types';

interface ConfigItemFormProps {
  item: ConfigItem;
  value: string;
  onChange: (key: string, value: string) => void;
}

export function ConfigItemForm({ item, value, onChange }: ConfigItemFormProps) {
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
          placeholder={`请选择${item.label}`}
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
            placeholder={`请输入${item.label}`}
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
            placeholder={`请输入${item.label}`}
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
            placeholder={`请输入${item.label}`}
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
            placeholder={`请输入${item.label}，如 https://example.com`}
          />
        );

      case 'string':
      default:
        return (
          <Input
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={`请输入${item.label}`}
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
          ? '当前已配置，显示为掩码'
          : undefined
      }
    >
      {renderControl()}
    </Form.Item>
  );
}
