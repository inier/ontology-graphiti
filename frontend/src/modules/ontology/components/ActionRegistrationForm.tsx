/**
 * ActionRegistrationForm 组件 —— Action Type 创建/编辑表单（FR-034 / T374）
 *
 * Form 字段：
 *   - name (Input, 必填，唯一性校验)
 *   - display_name (Input)
 *   - description (TextArea)
 *   - parameters (动态 Schema 编辑器 + JSON 预览)
 *   - return_type (Select)
 *   - linked_skill_id (Select, 关联已注册 Skill，可搜索)
 *   - opa_policy_id (Input, 可选)
 *   - preconditions (JSON 编辑器)
 *   - tags (Tag 输入)
 * 右侧"预览"卡片：实时展示 JSON
 * 底部：Cancel / Save / Save & Test
 * Save & Test：保存后跳转到测试页面（mock，console.log 参数）
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Input, Select, Button, Space, Row, Col, Typography, Tag, message, Empty, Alert,
} from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import {
  SaveOutlined, PlayCircleOutlined, CloseOutlined, PlusOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Title } = Typography;
const { TextArea } = Input;

export interface ActionRegistrationFormProps {
  actionId?: string;
  onClose?: () => void;
  onSaved?: (action: { id: string; name: string }) => void;
}

interface ParameterDef {
  name: string;
  type: 'string' | 'integer' | 'float' | 'boolean' | 'object' | 'array';
  required: boolean;
  description?: string;
  default_value?: string;
}

interface SkillOption {
  skill_id: string;
  name: string;
  description?: string;
}

interface ActionFormValues {
  name: string;
  display_name?: string;
  description?: string;
  return_type: string;
  linked_skill_id?: string;
  opa_policy_id?: string;
  preconditions?: string;
  tags: string[];
}

export function ActionRegistrationForm({ actionId, onClose, onSaved }: ActionRegistrationFormProps) {
  const { t } = useI18n('ontology');
  const [form] = Form.useForm<ActionFormValues>();
  const [parameters, setParameters] = useState<ParameterDef[]>([]);
  const [tagInput, setTagInput] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [skillOptions, setSkillOptions] = useState<SkillOption[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [preconditionsText, setPreconditionsText] = useState('');
  const [saving, setSaving] = useState(false);
  const [existingNames, setExistingNames] = useState<string[]>([]);
  const [actionName, setActionName] = useState<string>('');
  const [actionDisplayName, setActionDisplayName] = useState<string>('');
  const [actionDescription, setActionDescription] = useState<string>('');
  const [actionReturnType, setActionReturnType] = useState<string>('void');
  const [actionSkillId, setActionSkillId] = useState<string | undefined>();
  const [actionOpaPolicyId, setActionOpaPolicyId] = useState<string>('');

  const RETURN_TYPE_OPTIONS = useMemo(() => [
    { value: 'void', label: t('action.returnTypeVoid') },
    { value: 'boolean', label: 'boolean' },
    { value: 'object', label: 'object' },
    { value: 'array', label: 'array' },
    { value: 'string', label: 'string' },
    { value: 'integer', label: 'integer' },
    { value: 'float', label: 'float' },
  ], [t]);

  const PARAM_TYPE_OPTIONS = useMemo(() => [
    { value: 'string', label: 'string' },
    { value: 'integer', label: 'integer' },
    { value: 'float', label: 'float' },
    { value: 'boolean', label: 'boolean' },
    { value: 'object', label: 'object' },
    { value: 'array', label: 'array' },
  ], []);

  // ---- fetch skills ----
  const fetchSkills = useCallback(async () => {
    setSkillsLoading(true);
    try {
      const data = await apiClient.get<{ skills: SkillOption[] }>('/api/skills');
      setSkillOptions(data.skills || []);
    } catch (e) {
      message.error(t('action.loadSkillFailed', { msg: (e as Error).message }));
    } finally {
      setSkillsLoading(false);
    }
  }, [t]);

  const fetchExistingNames = useCallback(async () => {
    try {
      const data = await apiClient.get<{ action_types: Array<{ name: string }> }>('/api/ontology/action-types');
      setExistingNames((data.action_types || []).map((a) => a.name));
    } catch {
      setExistingNames([]);
    }
  }, []);

  const fetchAction = useCallback(async () => {
    if (!actionId) return;
    try {
      const data = await apiClient.get<{
        id: string;
        name: string;
        display_name?: string;
        description?: string;
        parameters?: ParameterDef[];
        return_type: string;
        linked_skill_id?: string;
        opa_policy_id?: string;
        preconditions?: Record<string, unknown> | null;
        tags?: string[];
      }>(`/api/ontology/action-types/${actionId}`);
      form.setFieldsValue({
        name: data.name,
        display_name: data.display_name,
        description: data.description,
        return_type: data.return_type,
        linked_skill_id: data.linked_skill_id,
        opa_policy_id: data.opa_policy_id,
        tags: data.tags || [],
      });
      setActionName(data.name);
      setActionDisplayName(data.display_name || '');
      setActionDescription(data.description || '');
      setActionReturnType(data.return_type);
      setActionSkillId(data.linked_skill_id);
      setActionOpaPolicyId(data.opa_policy_id || '');
      setParameters(data.parameters || []);
      setTags(data.tags || []);
      setPreconditionsText(data.preconditions ? JSON.stringify(data.preconditions, null, 2) : '');
    } catch (e) {
      message.error(t('action.loadActionFailed', { msg: (e as Error).message }));
    }
  }, [actionId, form, t]);

  useEffect(() => {
    void fetchSkills();
    void fetchExistingNames();
    void fetchAction();
  }, [fetchSkills, fetchExistingNames, fetchAction]);

  const addParameter = useCallback(() => {
    setParameters((prev) => [...prev, { name: '', type: 'string', required: false }]);
  }, []);

  const updateParameter = useCallback((idx: number, p: ParameterDef) => {
    setParameters((prev) => prev.map((it, i) => (i === idx ? p : it)));
  }, []);

  const removeParameter = useCallback((idx: number) => {
    setParameters((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const handleAddTag = useCallback(() => {
    const v = tagInput.trim();
    if (v && !tags.includes(v)) setTags((prev) => [...prev, v]);
    setTagInput('');
  }, [tagInput, tags]);

  const handleRemoveTag = useCallback((tag: string) => {
    setTags((prev) => prev.filter((x) => x !== tag));
  }, []);

  const previewJson = useMemo(() => {
    let preconditionsObj: unknown = null;
    if (preconditionsText.trim()) {
      try {
        preconditionsObj = JSON.parse(preconditionsText);
      } catch {
        preconditionsObj = '⚠️ 无效的 JSON';
      }
    }
    return {
      name: actionName,
      display_name: actionDisplayName,
      description: actionDescription,
      parameters: parameters.filter((p) => p.name).map((p) => ({
        name: p.name,
        type: p.type,
        required: p.required,
        description: p.description,
        default_value: p.default_value,
      })),
      return_type: actionReturnType,
      linked_skill_id: actionSkillId,
      opa_policy_id: actionOpaPolicyId || null,
      preconditions: preconditionsObj,
      tags,
    };
  }, [actionName, actionDisplayName, actionDescription, parameters, actionReturnType, actionSkillId, actionOpaPolicyId, preconditionsText, tags]);

  const validateAndCollect = useCallback(async () => {
    const values = await form.validateFields();
    let preconditions: Record<string, unknown> | null = null;
    if (preconditionsText.trim()) {
      try {
        preconditions = JSON.parse(preconditionsText);
      } catch {
        message.error(t('action.preconditionsError'));
        throw new Error('preconditions-json');
      }
    }
    const cleanedParams = parameters.filter((p) => p.name);
    return {
      ...values,
      tags: values.tags || [],
      parameters: cleanedParams,
      preconditions,
    };
  }, [form, preconditionsText, parameters, t]);

  const handleSave = useCallback(async (testAfter: boolean) => {
    let payload: Awaited<ReturnType<typeof validateAndCollect>>;
    try {
      payload = await validateAndCollect();
    } catch (e) {
      if ((e as Error).message === 'preconditions-json') return;
      return;
    }
    setSaving(true);
    try {
      const saved = actionId
        ? await apiClient.put<{ id: string; name: string }>(`/api/ontology/action-types/${actionId}`, payload)
        : await apiClient.post<{ id: string; name: string }>('/api/ontology/action-types', payload);
      message.success(actionId ? t('action.updated') : t('action.created'));
      onSaved?.(saved);
      if (testAfter) {
        console.log('[ActionRegistrationForm] Navigate to test page with params:', saved);
        try {
          await apiClient.post(`/api/ontology/action-types/${saved.id}/test`, {
            parameters: {},
          });
          message.info(t('action.testTriggered'));
        } catch {
          // 非阻塞
        }
      }
    } catch (e) {
      message.error(t('action.saveFailed', { msg: (e as Error).message }));
    } finally {
      setSaving(false);
    }
  }, [actionId, validateAndCollect, onSaved, t]);

  return (
    <div data-testid="action-registration-form" style={{ padding: 16 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} wrap>
        <Title level={3} style={{ margin: 0 }}>{actionId ? t('action.edit') : t('action.create')}</Title>
        {onClose && (
          <Button icon={<CloseOutlined />} onClick={onClose}>{t('action.close')}</Button>
        )}
      </Space>

      <Row gutter={16}>
        <Col xs={24} md={14}>
          <Card>
            <Form
              form={form}
              layout="vertical"
              initialValues={{ return_type: 'void', tags: [] }}
              onValuesChange={(_, all) => {
                setActionName(all.name || '');
                setActionDisplayName(all.display_name || '');
                setActionDescription(all.description || '');
                setActionReturnType(all.return_type || 'void');
                setActionSkillId(all.linked_skill_id);
                setActionOpaPolicyId(all.opa_policy_id || '');
              }}
            >
              <Form.Item
                name="name"
                label={t('action.name')}
                rules={[
                  { required: true, message: t('action.nameRequired') },
                  { pattern: /^[a-zA-Z][a-zA-Z0-9_]*$/, message: t('action.namePattern') },
                  {
                    validator: (_, value: string) => {
                      if (!value) return Promise.resolve();
                      if (actionId) return Promise.resolve();
                      if (existingNames.includes(value)) {
                        return Promise.reject(new Error(t('action.nameDuplicate')));
                      }
                      return Promise.resolve();
                    },
                  },
                ]}
              >
                <Input placeholder={t('action.namePlaceholder')} />
              </Form.Item>

              <Form.Item name="display_name" label={t('action.displayName')}>
                <Input placeholder={t('action.displayNamePlaceholder')} />
              </Form.Item>

              <Form.Item name="description" label={t('action.description')}>
                <TextArea rows={3} placeholder={t('action.descriptionPlaceholder')} />
              </Form.Item>

              <Form.Item label={t('action.parameters')}>
                {parameters.length === 0 ? (
                  <Empty description={t('action.noParameters')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
                ) : (
                  parameters.map((p, idx) => (
                    <Card
                      key={idx}
                      size="small"
                      style={{ marginBottom: 8 }}
                      extra={
                        <Button
                          type="text"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={() => removeParameter(idx)}
                        />
                      }
                    >
                      <Row gutter={8}>
                        <Col span={8}>
                          <Form.Item label={t('action.paramName')} style={{ marginBottom: 0 }}>
                            <Input
                              value={p.name}
                              placeholder={t('action.paramNamePlaceholder')}
                              onChange={(e) => updateParameter(idx, { ...p, name: e.target.value })}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={6}>
                          <Form.Item label={t('action.paramType')} style={{ marginBottom: 0 }}>
                            <Select
                              value={p.type}
                              onChange={(v) => updateParameter(idx, { ...p, type: v as ParameterDef['type'] })}
                              options={PARAM_TYPE_OPTIONS}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={4}>
                          <Form.Item label={t('action.paramRequired')} style={{ marginBottom: 0 }}>
                            <Select
                              value={p.required ? 'yes' : 'no'}
                              onChange={(v) => updateParameter(idx, { ...p, required: v === 'yes' })}
                              options={[{ value: 'yes', label: t('action.yes') }, { value: 'no', label: t('action.no') }]}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={6}>
                          <Form.Item label={t('action.paramDefault')} style={{ marginBottom: 0 }}>
                            <Input
                              value={p.default_value || ''}
                              placeholder={t('action.paramDefaultPlaceholder')}
                              onChange={(e) => updateParameter(idx, { ...p, default_value: e.target.value })}
                            />
                          </Form.Item>
                        </Col>
                      </Row>
                    </Card>
                  ))
                )}
                <Button
                  type="dashed"
                  icon={<PlusOutlined />}
                  onClick={addParameter}
                  block
                  style={{ marginTop: 8 }}
                >
                  {t('action.addParameter')}
                </Button>
              </Form.Item>

              <Form.Item name="return_type" label={t('action.returnType')} rules={[{ required: true, message: t('action.returnTypeRequired') }]}>
                <Select options={RETURN_TYPE_OPTIONS} />
              </Form.Item>

              <Form.Item name="linked_skill_id" label={t('action.linkedSkill')}>
                <Select
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  loading={skillsLoading}
                  placeholder={t('action.selectSkill')}
                  options={skillOptions.map((s) => ({ value: s.skill_id, label: s.name }))}
                />
              </Form.Item>

              <Form.Item name="opa_policy_id" label={t('action.opaPolicyId')}>
                <Input placeholder={t('action.opaPolicyPlaceholder')} />
              </Form.Item>

              <Form.Item label={t('action.preconditions')}>
                <TextArea
                  rows={4}
                  value={preconditionsText}
                  onChange={(e) => setPreconditionsText(e.target.value)}
                  placeholder={t('action.preconditionsPlaceholder')}
                />
                {preconditionsText.trim() && (() => {
                  try {
                    JSON.parse(preconditionsText);
                    return null;
                  } catch {
                    return <Alert type="error" showIcon title={t('action.preconditionsInvalid')} style={{ marginTop: 4 }} />;
                  }
                })()}
              </Form.Item>

              <Form.Item label={t('action.tags')}>
                <Space.Compact style={{ width: '100%' }}>
                  <Input
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onPressEnter={(e) => { e.preventDefault(); handleAddTag(); }}
                    placeholder={t('action.tagInputPlaceholder')}
                  />
                  <Button type="primary" onClick={handleAddTag}>{t('action.addTag')}</Button>
                </Space.Compact>
                <div style={{ marginTop: 8 }}>
                  {tags.length === 0 ? (
                    <Text type="secondary" style={{ fontSize: 12 }}>{t('action.noTags')}</Text>
                  ) : (
                    tags.map((tag) => (
                      <Tag
                        key={tag}
                        color="blue"
                        closable
                        onClose={() => handleRemoveTag(tag)}
                        style={{ marginBottom: 4 }}
                      >
                        {tag}
                      </Tag>
                    ))
                  )}
                </div>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} md={10}>
          <Card title={t('action.jsonPreview')} size="small">
            <pre
              style={{
                background: '#fafafa',
                padding: 12,
                borderRadius: 4,
                maxHeight: 600,
                overflow: 'auto',
                fontSize: 12,
                fontFamily: 'monospace',
              }}
            >
              {JSON.stringify(previewJson, null, 2)}
            </pre>
          </Card>
        </Col>
      </Row>

      <div style={{ marginTop: 16, textAlign: 'right' }}>
        <Space>
          {onClose && <Button onClick={onClose}>{t('action.cancel')}</Button>}
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            onClick={() => handleSave(false)}
          >
            {t('action.save')}
          </Button>
          <Button
            type="primary"
            ghost
            icon={<PlayCircleOutlined />}
            loading={saving}
            onClick={() => handleSave(true)}
          >
            {t('action.saveAndTest')}
          </Button>
        </Space>
      </div>
    </div>
  );
}

export default ActionRegistrationForm;
