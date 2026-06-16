import { useState, useEffect } from 'react';
import { 
  Modal, Form, Input, Select, Tabs, Button, Space, Typography, 
  Divider, Card, Collapse, message
} from 'antd';
import { 
  SaveOutlined, PlusOutlined,
  CodeOutlined, EditOutlined
} from '@ant-design/icons';

const { Text } = Typography;
const { TextArea } = Input;


interface SkillDefinition {
  name: string;
  description: string;
  category: string;
  triggers: string[];
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  sections?: {
    description?: string;
    instructions?: string;
    examples?: string;
    notes?: string;
  };
}

interface SkillEditorProps {
  skill?: SkillDefinition;
  visible: boolean;
  onSave: (skill: SkillDefinition) => void;
  onCancel: () => void;
}

const categoryOptions = [
  { value: 'intelligence', label: '情报 (intelligence)' },
  { value: 'analysis', label: '分析 (analysis)' },
  { value: 'visualization', label: '可视化 (visualization)' },
  { value: 'data_ingestion', label: '数据摄入 (data_ingestion)' },
  { value: 'ontology_builder', label: '本体构建 (ontology_builder)' },
  { value: 'custom', label: '自定义 (custom)' },
];

export function SkillEditor({ skill, visible, onSave, onCancel }: SkillEditorProps) {
  const [form] = Form.useForm();
  const [activeTab, setActiveTab] = useState('basic');
  const [inputSchemaText, setInputSchemaText] = useState('');
  const [outputSchemaText, setOutputSchemaText] = useState('');

  const formValues = Form.useWatch([], form) ?? {};

  useEffect(() => {
    if (skill) {
      form.setFieldsValue({
        name: skill.name,
        description: skill.description,
        category: skill.category,
        triggers: skill.triggers?.join(', '),
        sections: skill.sections || {},
      });
      setInputSchemaText(JSON.stringify(skill.input_schema || {}, null, 2));
      setOutputSchemaText(JSON.stringify(skill.output_schema || {}, null, 2));
    } else {
      form.resetFields();
      setInputSchemaText('{\n  \n}');
      setOutputSchemaText('{\n  \n}');
    }
  }, [skill, open, form]);

  const handleSave = () => {
    const values = form.getFieldsValue();
    
    try {
      const inputSchema = JSON.parse(inputSchemaText);
      const outputSchema = JSON.parse(outputSchemaText);
      
      const skillDef: SkillDefinition = {
        name: values.name,
        description: values.description,
        category: values.category,
        triggers: values.triggers?.split(',').map((t: string) => t.trim()).filter(Boolean) || [],
        input_schema: inputSchema,
        output_schema: outputSchema,
        sections: values.sections,
      };
      
      onSave(skillDef);
    } catch (e) {
      message.error('JSON Schema 格式不正确，请检查');
    }
  };

  const generateMarkdown = () => {
    const values = formValues;
    const triggers = values.triggers?.split(',').map((t: string) => t.trim()).filter(Boolean) || [];
    
    return `# ${values.name}

## Description

${values.description || 'TODO: 描述此 Skill 的功能'}

## Triggers

${triggers.length > 0 ? triggers.map((t: string) => `- ${t}`).join('\n') : '- TODO: 添加触发关键词'}

## Input Schema

\`\`\`json
${inputSchemaText}
\`\`\`

## Output Schema

\`\`\`json
${outputSchemaText}
\`\`\`

${values.sections?.instructions ? `## Instructions

${values.sections.instructions}` : ''}

${values.sections?.examples ? `## Examples

${values.sections.examples}` : ''}

${values.sections?.notes ? `## Notes

${values.sections.notes}` : ''}
`;
  };

  return (
    <Modal
      title={skill ? '编辑 Skill' : '创建新 Skill'}
      open={open}
      onCancel={onCancel}
      width={900}
      footer={
        <Space>
          <Button onClick={onCancel}>取消</Button>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>
            保存
          </Button>
        </Space>
      }
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'basic',
            label: '基本信息',
            children: (
              <Form form={form} layout="vertical">
                <Form.Item
                  name="name"
                  label="Skill 名称"
                  rules={[{ required: true, message: '请输入 Skill 名称' }]}
                >
                  <Input placeholder="例如: location_query" />
                </Form.Item>

                <Form.Item
                  name="category"
                  label="分类"
                  rules={[{ required: true, message: '请选择分类' }]}
                >
                  <Select options={categoryOptions} placeholder="选择分类" />
                </Form.Item>

                <Form.Item
                  name="triggers"
                  label="触发关键词"
                  tooltip="多个关键词用逗号分隔"
                >
                  <Input placeholder="例如: 查询位置, 部队位置, 单位位置" />
                </Form.Item>

                <Form.Item
                  name="description"
                  label="简短描述"
                  rules={[{ required: true, message: '请输入描述' }]}
                >
                  <TextArea rows={2} placeholder="简要描述此 Skill 的功能" />
                </Form.Item>

                <Form.Item
                  name={['sections', 'instructions']}
                  label="使用说明"
                >
                  <TextArea rows={4} placeholder="详细的使用说明和参数说明..." />
                </Form.Item>
              </Form>
            ),
          },
          {
            key: 'schema',
            label: 'Schema 定义',
            children: (
              <div>
                <div style={{ marginBottom: 16 }}>
                  <Button 
                    type="link" 
                    icon={<PlusOutlined />} 
                    onClick={() => {
                      try {
                        const current = JSON.parse(inputSchemaText);
                        current['new_field'] = { type: 'string', description: 'TODO' };
                        setInputSchemaText(JSON.stringify(current, null, 2));
                      } catch {
                        // ignore
                      }
                    }}
                  >
                    添加输入字段
                  </Button>
                </div>
                
                <div style={{ display: 'flex', gap: 24 }}>
                  <div style={{ flex: 1 }}>
                    <Text strong>输入 Schema:</Text>
                    <Card size="small" style={{ marginTop: 8 }}>
                      <TextArea
                        value={inputSchemaText}
                        onChange={(e) => setInputSchemaText(e.target.value)}
                        rows={12}
                        style={{ fontFamily: 'Monaco, Consolas, monospace', fontSize: 12 }}
                      />
                    </Card>
                  </div>
                  <div style={{ flex: 1 }}>
                    <Text strong>输出 Schema:</Text>
                    <Card size="small" style={{ marginTop: 8 }}>
                      <TextArea
                        value={outputSchemaText}
                        onChange={(e) => setOutputSchemaText(e.target.value)}
                        rows={12}
                        style={{ fontFamily: 'Monaco, Consolas, monospace', fontSize: 12 }}
                      />
                    </Card>
                  </div>
                </div>

                <Divider />

                <div>
                  <Text strong>高级设置:</Text>
                  <Collapse style={{ marginTop: 8 }} items={[
                    { key: 'examples', label: '示例 (Examples)', children: <Form.Item name={['sections', 'examples']}><TextArea rows={4} placeholder="添加使用示例..." /></Form.Item> },
                    { key: 'notes', label: '注意事项 (Notes)', children: <Form.Item name={['sections', 'notes']}><TextArea rows={3} placeholder="添加注意事项..." /></Form.Item> },
                  ]} />
                </div>
              </div>
            ),
          },
          {
            key: 'preview',
            label: '预览',
            children: (
              <div>
                <div style={{ marginBottom: 16 }}>
                  <Button 
                    icon={<EditOutlined />} 
                    onClick={() => setActiveTab('basic')}
                  >
                    返回编辑
                  </Button>
                </div>
                <Card>
                  <pre style={{ 
                    whiteSpace: 'pre-wrap', 
                    fontFamily: 'Monaco, Consolas, monospace',
                    fontSize: 13,
                    background: '#f5f5f5',
                    padding: 16,
                    borderRadius: 8,
                    maxHeight: 500,
                    overflow: 'auto'
                  }}>
                    {generateMarkdown()}
                  </pre>
                </Card>
              </div>
            ),
          },
        ]}
      />
    </Modal>
  );
}

// 简化版 Skill 快速编辑
interface QuickSkillEditorProps {
  initialData?: Partial<SkillDefinition>;
  onSave: (skill: Partial<SkillDefinition>) => void;
}

export function QuickSkillEditor({ initialData, onSave }: QuickSkillEditorProps) {
  const [name, setName] = useState(initialData?.name || '');
  const [description, setDescription] = useState(initialData?.description || '');
  const [category, setCategory] = useState(initialData?.category || 'custom');

  const handleSave = () => {
    if (!name.trim()) {
      message.error('请输入 Skill 名称');
      return;
    }
    onSave({ name, description, category });
  };

  return (
    <Card size="small">
      <Space orientation="vertical" style={{ width: '100%' }}>
        <Input
          placeholder="Skill 名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
          prefix={<CodeOutlined />}
        />
        <Input
          placeholder="简短描述"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <Space>
          <Select
            value={category}
            onChange={setCategory}
            options={categoryOptions}
            style={{ width: 160 }}
          />
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>
            保存
          </Button>
        </Space>
      </Space>
    </Card>
  );
}

export default SkillEditor;
