/** 渠道配置表单组件 */

import React, { useEffect } from 'react';
import { Form, Input, Select, Switch, Button, Space, message, Alert } from 'antd';
import type { ChannelType, ChannelTypeInfo } from '../types';
import { CHANNEL_TYPE_NAMES, CHANNEL_ICONS } from '../types';

interface ChannelConfigFormProps {
  channelTypes: ChannelTypeInfo[];
  initialValues?: {
    name?: string;
    channel_type?: ChannelType;
    enabled?: boolean;
    allow_from?: string[];
    config?: Record<string, any>;
  };
  onSubmit: (values: {
    name: string;
    channel_type: ChannelType;
    enabled: boolean;
    allow_from: string[];
    config: Record<string, any>;
  }) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
}

export const ChannelConfigForm: React.FC<ChannelConfigFormProps> = ({
  channelTypes,
  initialValues,
  onSubmit,
  onCancel,
  loading,
}) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (initialValues) {
      form.setFieldsValue(initialValues);
    }
  }, [initialValues, form]);

  const selectedType = Form.useWatch('channel_type', form);

  const currentTypeInfo = channelTypes.find((t) => t.type === selectedType);

  const handleFinish = async (values: any) => {
    try {
      await onSubmit({
        name: values.name,
        channel_type: values.channel_type,
        enabled: values.enabled || false,
        allow_from: values.allow_from || ['*'],
        config: values.config || {},
      });
      message.success('保存成功');
    } catch {
      message.error('保存失败');
    }
  };

  const renderConfigFields = () => {
    if (!currentTypeInfo) {
      return <Alert title="请先选择渠道类型" type="info" />;
    }

    const fields: React.ReactNode[] = [];

    // 必填字段
    currentTypeInfo.required_fields.forEach((field) => {
      if (field.includes('token') || field.includes('secret') || field.includes('password') || field.includes('key')) {
        fields.push(
          <Form.Item
            key={field}
            name={['config', field]}
            label={field}
            rules={[{ required: true, message: `请输入 ${field}` }]}
          >
            <Input.Password placeholder={`请输入 ${field}`} />
          </Form.Item>
        );
      } else if (field.includes('port')) {
        fields.push(
          <Form.Item
            key={field}
            name={['config', field]}
            label={field}
            rules={[{ required: true, message: `请输入 ${field}` }]}
          >
            <Input type="number" placeholder={`请输入 ${field}`} />
          </Form.Item>
        );
      } else {
        fields.push(
          <Form.Item
            key={field}
            name={['config', field]}
            label={field}
            rules={[{ required: true, message: `请输入 ${field}` }]}
          >
            <Input placeholder={`请输入 ${field}`} />
          </Form.Item>
        );
      }
    });

    // 可选字段
    currentTypeInfo.optional_fields.forEach((field) => {
      if (field.includes('token') || field.includes('secret') || field.includes('password') || field.includes('key')) {
        fields.push(
          <Form.Item
            key={field}
            name={['config', field]}
            label={field}
          >
            <Input.Password placeholder={`请输入 ${field}（可选）`} />
          </Form.Item>
        );
      } else if (field.includes('port')) {
        fields.push(
          <Form.Item
            key={field}
            name={['config', field]}
            label={field}
          >
            <Input type="number" placeholder={`请输入 ${field}（可选）`} />
          </Form.Item>
        );
      } else {
        fields.push(
          <Form.Item
            key={field}
            name={['config', field]}
            label={field}
          >
            <Input placeholder={`请输入 ${field}（可选）`} />
          </Form.Item>
        );
      }
    });

    return fields.length > 0 ? fields : <Alert title="该渠道无需额外配置" type="info" />;
  };

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleFinish}
      initialValues={{
        name: initialValues?.name || '',
        channel_type: initialValues?.channel_type,
        enabled: initialValues?.enabled || false,
        allow_from: initialValues?.allow_from || ['*'],
        config: initialValues?.config || {},
      }}
    >
      <Form.Item
        name="name"
        label="配置名称"
        rules={[{ required: true, message: '请输入配置名称' }]}
      >
        <Input placeholder="例如：生产环境飞书" />
      </Form.Item>

      <Form.Item
        name="channel_type"
        label="渠道类型"
        rules={[{ required: true, message: '请选择渠道类型' }]}
      >
        <Select placeholder="请选择渠道类型">
          {channelTypes.map((type) => (
            <Select.Option key={type.type} value={type.type}>
              <Space>
                <span>{CHANNEL_ICONS[type.type]}</span>
                <span>{type.name}</span>
              </Space>
            </Select.Option>
          ))}
        </Select>
      </Form.Item>

      <Form.Item name="enabled" label="启用" valuePropName="checked">
        <Switch />
      </Form.Item>

      <Form.Item name="allow_from" label="允许访问的用户">
        <Select mode="tags" placeholder="留空表示允许所有人，或输入用户 ID">
          <Select.Option value="*">所有人</Select.Option>
        </Select>
      </Form.Item>

      <div style={{ marginBottom: 16, fontWeight: 500 }}>渠道配置</div>

      {renderConfigFields()}

      <Form.Item style={{ marginTop: 24 }}>
        <Space>
          <Button type="primary" htmlType="submit" loading={loading}>
            保存
          </Button>
          <Button onClick={onCancel}>取消</Button>
        </Space>
      </Form.Item>
    </Form>
  );
};
