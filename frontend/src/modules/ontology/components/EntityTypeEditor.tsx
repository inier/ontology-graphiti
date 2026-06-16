import { useState, useEffect } from 'react';
import { Card, Form, Row, Col, Divider, Empty } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import adapter from '@/modules/shared/components/adapter';
import { PropertyEditor } from './PropertyEditor';
import { RelationEditor } from './RelationEditor';
import type { EntityType, PropertyDefinition, RelationDefinition } from '../services/ontologyApi';

interface EntityTypeEditorProps {
  entityType: EntityType | null;
  allEntityTypes: EntityType[];
  onSave: (data: Partial<EntityType>) => void;
}

const Button = adapter.getButton();
const Input = adapter.getInput();
const Select = adapter.getSelect();

const CLASSIFICATION_OPTIONS = [
  { label: 'TS - 绝密', value: 'TS' },
  { label: 'S - 机密', value: 'S' },
  { label: 'C - 秘密', value: 'C' },
  { label: 'U - 公开', value: 'U' },
];

export function EntityTypeEditor({ entityType, allEntityTypes, onSave }: EntityTypeEditorProps) {
  const [formData, setFormData] = useState<{
    name: string;
    display_name: string;
    description: string;
    classification_level: 'TS' | 'S' | 'C' | 'U';
    properties: PropertyDefinition[];
    primary_key: string;
    relations: RelationDefinition[];
  }>({
    name: '',
    display_name: '',
    description: '',
    classification_level: 'U',
    properties: [],
    primary_key: '',
    relations: [],
  });

  useEffect(() => {
    if (entityType) {
      setFormData({
        name: entityType.name,
        display_name: entityType.display_name,
        description: entityType.description,
        classification_level: entityType.classification_level,
        properties: [...entityType.properties],
        primary_key: entityType.primary_key || '',
        relations: [...entityType.relations],
      });
    } else {
      setFormData({
        name: '',
        display_name: '',
        description: '',
        classification_level: 'U',
        properties: [],
        primary_key: '',
        relations: [],
      });
    }
  }, [entityType]);

  const updateField = <K extends keyof typeof formData>(key: K, value: (typeof formData)[K]) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  const handlePropertyChange = (index: number, property: PropertyDefinition) => {
    const newProperties = [...formData.properties];
    newProperties[index] = property;
    updateField('properties', newProperties);
  };

  const handlePropertyRemove = (index: number) => {
    const newProperties = formData.properties.filter((_, i) => i !== index);
    updateField('properties', newProperties);
  };

  const handleAddProperty = () => {
    const newProperty: PropertyDefinition = {
      name: '',
      data_type: 'string',
      required: false,
      classification_level: 'U',
    };
    updateField('properties', [...formData.properties, newProperty]);
  };

  const handleRelationChange = (index: number, relation: RelationDefinition) => {
    const newRelations = [...formData.relations];
    newRelations[index] = relation;
    updateField('relations', newRelations);
  };

  const handleRelationRemove = (index: number) => {
    const newRelations = formData.relations.filter((_, i) => i !== index);
    updateField('relations', newRelations);
  };

  const handleAddRelation = () => {
    const newRelation: RelationDefinition = {
      name: '',
      target_type: '',
      cardinality: '1:N',
      link_type: 'association',
    };
    updateField('relations', [...formData.relations, newRelation]);
  };

  const handleSave = () => {
    onSave(formData);
  };

  const primaryKeyOptions = formData.properties
    .filter((p) => p.name)
    .map((p) => ({ label: p.name, value: p.name }));

  if (!entityType) {
    return (
      <Card>
        <Empty description="请选择一个实体类型" />
      </Card>
    );
  }

  return (
    <div style={{ height: '100%', overflow: 'auto' }}>
      <Card
        title={entityType.display_name || entityType.name}
        extra={
          <Button type="primary" onClick={handleSave}>
            保存
          </Button>
        }
      >
        <Form layout="vertical">
          <Row gutter={[16, 0]}>
            <Col span={8}>
              <Form.Item label="名称">
                <Input
                  value={formData.name}
                  onChange={(val) => updateField('name', val)}
                  placeholder="entity_type_name"
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="显示名称">
                <Input
                  value={formData.display_name}
                  onChange={(val) => updateField('display_name', val)}
                  placeholder="显示名称"
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="密级">
                <Select
                  value={formData.classification_level}
                  onChange={(val) => updateField('classification_level', val)}
                  options={CLASSIFICATION_OPTIONS}
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="描述">
            <Input
              value={formData.description}
              onChange={(val) => updateField('description', val)}
              placeholder="描述"
            />
          </Form.Item>
          <Form.Item label="主键">
            <Select
              value={formData.primary_key || undefined}
              onChange={(val) => updateField('primary_key', val)}
              options={primaryKeyOptions}
              placeholder="选择主键属性"
            />
          </Form.Item>
        </Form>

        <Divider orientation={"left" as React.ComponentProps<typeof Divider>['orientation']}>属性列表</Divider>
        {formData.properties.map((prop, idx) => (
          <PropertyEditor
            key={idx}
            property={prop}
            index={idx}
            onChange={handlePropertyChange}
            onRemove={handlePropertyRemove}
          />
        ))}
        <Button
          type="dashed"
          icon={<PlusOutlined />}
          onClick={handleAddProperty}
          style={{ width: '100%', marginBottom: 16 }}
        >
          新增属性
        </Button>

        <Divider orientation={"left" as React.ComponentProps<typeof Divider>['orientation']}>关系列表</Divider>
        {formData.relations.map((rel, idx) => (
          <RelationEditor
            key={idx}
            relation={rel}
            index={idx}
            entityTypes={allEntityTypes}
            onChange={handleRelationChange}
            onRemove={handleRelationRemove}
          />
        ))}
        <Button
          type="dashed"
          icon={<PlusOutlined />}
          onClick={handleAddRelation}
          style={{ width: '100%' }}
        >
          新增关系
        </Button>
      </Card>
    </div>
  );
}
