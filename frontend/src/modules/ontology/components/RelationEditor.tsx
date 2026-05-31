import { useState } from 'react';
import { Card, Form, Row, Col } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import adapter from '../../shared/components/adapter';
import type { RelationDefinition } from '../services/ontologyApi';

interface RelationEditorProps {
  relation: RelationDefinition;
  index: number;
  entityTypes: Array<{ name: string; display_name: string }>;
  onChange: (index: number, relation: RelationDefinition) => void;
  onRemove: (index: number) => void;
}

const Button = adapter.getButton();
const Input = adapter.getInput();
const Select = adapter.getSelect();

const CARDINALITY_OPTIONS = [
  { label: '1:1', value: '1:1' },
  { label: '1:N', value: '1:N' },
  { label: 'N:1', value: 'N:1' },
  { label: 'N:N', value: 'N:N' },
];

const LINK_TYPE_OPTIONS = [
  { label: 'Association', value: 'association' },
  { label: 'Composition', value: 'composition' },
  { label: 'Dependency', value: 'dependency' },
  { label: 'Inheritance', value: 'inheritance' },
];

export function RelationEditor({ relation, index, entityTypes, onChange, onRemove }: RelationEditorProps) {
  const [localRelation, setLocalRelation] = useState<RelationDefinition>(relation);

  const updateField = <K extends keyof RelationDefinition>(key: K, value: RelationDefinition[K]) => {
    const updated = { ...localRelation, [key]: value };
    setLocalRelation(updated);
    onChange(index, updated);
  };

  const targetTypeOptions = entityTypes.map((et) => ({
    label: et.display_name || et.name,
    value: et.name,
  }));

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
          <Form.Item label="关系名" style={{ marginBottom: 0 }}>
            <Input
              value={localRelation.name}
              onChange={(val) => updateField('name', val)}
              placeholder="relation_name"
            />
          </Form.Item>
        </Col>
        <Col span={6}>
          <Form.Item label="目标类型" style={{ marginBottom: 0 }}>
            <Select
              value={localRelation.target_type}
              onChange={(val) => updateField('target_type', val)}
              options={targetTypeOptions}
              placeholder="选择目标类型"
            />
          </Form.Item>
        </Col>
        <Col span={6}>
          <Form.Item label="基数" style={{ marginBottom: 0 }}>
            <Select
              value={localRelation.cardinality}
              onChange={(val) => updateField('cardinality', val)}
              options={CARDINALITY_OPTIONS}
            />
          </Form.Item>
        </Col>
        <Col span={6}>
          <Form.Item label="关联类型" style={{ marginBottom: 0 }}>
            <Select
              value={localRelation.link_type}
              onChange={(val) => updateField('link_type', val)}
              options={LINK_TYPE_OPTIONS}
            />
          </Form.Item>
        </Col>
      </Row>
    </Card>
  );
}
