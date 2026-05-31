import { useState } from 'react';
import { Card, Form, Switch, Row, Col } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import adapter from '../../shared/components/adapter';
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

const DATA_TYPE_OPTIONS = [
  { label: 'String', value: 'string' },
  { label: 'Integer', value: 'integer' },
  { label: 'Float', value: 'float' },
  { label: 'Boolean', value: 'boolean' },
  { label: 'Date', value: 'date' },
  { label: 'DateTime', value: 'datetime' },
  { label: 'JSON', value: 'json' },
  { label: 'Array', value: 'array' },
];

const CLASSIFICATION_OPTIONS = [
  { label: 'TS', value: 'TS' },
  { label: 'S', value: 'S' },
  { label: 'C', value: 'C' },
  { label: 'U', value: 'U' },
];

export function PropertyEditor({ property, index, onChange, onRemove }: PropertyEditorProps) {
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
          <Form.Item label="属性名" style={{ marginBottom: 0 }}>
            <Input
              value={localProperty.name}
              onChange={(val) => updateField('name', val)}
              placeholder="property_name"
            />
          </Form.Item>
        </Col>
        <Col span={5}>
          <Form.Item label="数据类型" style={{ marginBottom: 0 }}>
            <Select
              value={localProperty.data_type}
              onChange={(val) => updateField('data_type', val)}
              options={DATA_TYPE_OPTIONS}
            />
          </Form.Item>
        </Col>
        <Col span={4}>
          <Form.Item label="必填" style={{ marginBottom: 0 }}>
            <Switch
              checked={localProperty.required}
              onChange={(val) => updateField('required', val)}
            />
          </Form.Item>
        </Col>
        <Col span={5}>
          <Form.Item label="默认值" style={{ marginBottom: 0 }}>
            <Input
              value={localProperty.default_value || ''}
              onChange={(val) => updateField('default_value', val)}
              placeholder="default"
            />
          </Form.Item>
        </Col>
        <Col span={4}>
          <Form.Item label="密级" style={{ marginBottom: 0 }}>
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
