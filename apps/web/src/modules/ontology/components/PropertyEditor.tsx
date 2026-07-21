import { useState } from 'react';
import { Switch, Row, Col } from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import { ProCard as Card } from '@ant-design/pro-components';
import { DeleteOutlined } from '@ant-design/icons';
import adapter from '@/modules/shared/components/adapter';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { PropertyDefinition } from '../services/ontologyApi';

interface PropertyEditorProps {
  property: PropertyDefinition;
  index: number;
  onChange: (index: number, property: PropertyDefinition) => void;
  onRemove: (index: number) => void;
}

const Button = adapter.getButton();
const Input = adapter.getInput();
const Select = adapter.getSelect();

export function PropertyEditor({ property, index, onChange, onRemove }: PropertyEditorProps) {
  const { t } = useI18n('ontology');

  const DATA_TYPE_OPTIONS = [
    { label: t('字符串'), value: 'string' },
    { label: t('整数'), value: 'integer' },
    { label: t('浮点数'), value: 'float' },
    { label: t('布尔值'), value: 'boolean' },
    { label: t('日期'), value: 'date' },
    { label: t('日期时间'), value: 'datetime' },
    { label: t('JSON'), value: 'json' },
    { label: t('数组'), value: 'array' },
  ];

  const CLASSIFICATION_OPTIONS = [
    { label: 'TS', value: 'TS' },
    { label: 'S', value: 'S' },
    { label: 'C', value: 'C' },
    { label: 'U', value: 'U' },
  ];

  const [localProperty, setLocalProperty] = useState<PropertyDefinition>(property);

  const updateField = <K extends keyof PropertyDefinition>(key: K, value: PropertyDefinition[K]) => {
    const updated = { ...localProperty, [key]: value };
    setLocalProperty(updated);
    onChange(index, updated);
  };

  return (
    <Card
      size="small"
      style={{ marginBottom: 8 }}
      extra={
        <Button
          type="text"
          danger
          icon={<DeleteOutlined />}
          onClick={() => onRemove(index)}
        />
      }
    >
      <Row gutter={[8, 8]}>
        <Col span={6}>
          <Form.Item label={t('属性名')} style={{ marginBottom: 0 }}>
            <Input
              value={localProperty.name}
              onChange={(val) => updateField('name', val)}
              placeholder="property_name"
            />
          </Form.Item>
        </Col>
        <Col span={5}>
          <Form.Item label={t('数据类型')} style={{ marginBottom: 0 }}>
            <Select
              value={localProperty.data_type}
              onChange={(val) => updateField('data_type', val)}
              options={DATA_TYPE_OPTIONS}
            />
          </Form.Item>
        </Col>
        <Col span={4}>
          <Form.Item label={t('必填')} style={{ marginBottom: 0 }}>
            <Switch
              checked={localProperty.required}
              onChange={(val) => updateField('required', val)}
            />
          </Form.Item>
        </Col>
        <Col span={5}>
          <Form.Item label={t('默认值')} style={{ marginBottom: 0 }}>
            <Input
              value={localProperty.default_value || ''}
              onChange={(val) => updateField('default_value', val)}
              placeholder="default"
            />
          </Form.Item>
        </Col>
        <Col span={4}>
          <Form.Item label={t('密级')} style={{ marginBottom: 0 }}>
            <Select
              value={localProperty.classification_level}
              onChange={(val) => updateField('classification_level', val)}
              options={CLASSIFICATION_OPTIONS}
            />
          </Form.Item>
        </Col>
      </Row>
    </Card>
  );
}
