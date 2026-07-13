/**
 * 术语 Modal 表单：新建/编辑
 * 字段：canonical / en / semantic_type Select /
 *       synonyms Chips / near_synonyms TextArea / aliases TextArea /
 *       stoplist Switch
 */
import React, { useEffect } from 'react';
import {
  Modal,
  Form,
  Input,
  Select,
  Switch,
  App,
  Space,
  Alert,
  Chips,
  Typography,
} from 'antd';
import type { SemanticType, UslTerm, TermPayload } from '../types';
import {
  SEMANTIC_TYPE_LABEL,
  SEMANTIC_TYPE_COLOR,
} from '../types';
import { createTerm, updateTerm } from '../services/uslApi';
import { useSemanticAdminStore } from '../store/useSemanticAdminStore';
import { useUslPermissions } from '../hooks/useUslPermissions';

const { TextArea } = Input;
const { Text } = Typography;

export interface TermFormValues {
  canonical: string;
  semantic_type: SemanticType;
  synonyms?: string[];
  near_synonyms_text?: string;
  aliases_text?: string;
  stoplist?: boolean;
}

interface TermFormProps {
  open: boolean;
  mode: 'create' | 'edit';
  initial?: UslTerm;
  onCancel: () => void;
  onSubmitted: () => void;
}

function splitLinesToStrings(text?: string): string[] {
  if (!text) return [];
  return text
    .split(/[,，、\n]/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

export function TermForm({ open, mode, initial, onCancel, onSubmitted }: TermFormProps) {
  const { message } = App.useApp();
  const { canWrite } = useUslPermissions();
  const currentDomain = useSemanticAdminStore((s) => s.currentDomain);
  const [form] = Form.useForm<TermFormValues>();
  const [submitting, setSubmitting] = React.useState(false);

  useEffect(() => {
    if (!open) return;
    if (initial) {
      form.setFieldsValue({
        canonical: initial.canonical,
        semantic_type: initial.semantic_type,
        synonyms: initial.synonyms || [],
        near_synonyms_text: (initial.near_synonyms || []).join('、'),
        aliases_text: (initial.aliases || []).join('、'),
        stoplist: !!initial.stoplist,
      });
    } else {
      form.resetFields();
      form.setFieldsValue({
        semantic_type: '对象类型' as SemanticType,
        stoplist: false,
        synonyms: [],
      });
    }
  }, [open, initial, form]);

  const semanticTypeOptions = (
    Object.entries(SEMANTIC_TYPE_LABEL) as Array<[SemanticType, string]>
  ).map(([v, l]) => ({
    label: (
      <Space size="small">
        <span
          style={{
            display: 'inline-block',
            width: 8,
            height: 8,
            borderRadius: 2,
            background: `var(--ant-color-${SEMANTIC_TYPE_COLOR[v]}-6, #${SEMANTIC_TYPE_COLOR[v] === 'blue' ? '1677ff' : '52c41a'})`,
          }}
        />
        <span>{l}</span>
      </Space>
    ),
    value: v,
  }));

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (!currentDomain) {
        message.error('未选择语义域，请先在「语义域列表」中选择');
        return;
      }
      const payload: TermPayload = {
        domain_id: currentDomain.code,
        canonical: values.canonical.trim(),
        semantic_type: values.semantic_type,
        synonyms: values.synonyms?.filter((s) => s && s.trim()) || [],
        near_synonyms: splitLinesToStrings(values.near_synonyms_text),
        aliases: splitLinesToStrings(values.aliases_text),
        stoplist: !!values.stoplist,
      };

      setSubmitting(true);
      if (mode === 'create') {
        const created = await createTerm(payload);
        message.success(`术语「${created.canonical}」创建成功`);
      } else if (mode === 'edit' && initial?.id) {
        const updated = await updateTerm(initial.id, payload);
        message.success(`术语「${updated.canonical}」更新成功`);
      } else if (mode === 'edit' && !initial?.id) {
        message.warning('当前行无 ID，无法更新（请确认后端已持久化该术语）');
      }
      onSubmitted();
    } catch (err) {
      if (err instanceof Error && !String(err.message).includes('validate')) {
        message.error(err.message || '提交失败');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title={mode === 'create' ? '新建规范术语' : `编辑术语 ${initial?.canonical || ''}`}
      open={open}
      onCancel={onCancel}
      destroyOnHidden
      width={600}
      okText={mode === 'create' ? '创建' : '保存'}
      cancelText="取消"
      okButtonProps={{ disabled: !canWrite, loading: submitting }}
      onOk={handleOk}
    >
      {!currentDomain && (
        <Alert
          type="warning"
          showIcon
          message="未选择语义域，将无法提交"
          style={{ marginBottom: 16 }}
        />
      )}
      {!canWrite && (
        <Alert
          type="warning"
          showIcon
          message="当前角色无写权限（需要 admin / schema_auditor），仅可查看"
          style={{ marginBottom: 16 }}
        />
      )}
      <Form form={form} layout="vertical" requiredMark="optional" preserve={false}>
        <Form.Item
          label="规范词 canonical"
          name="canonical"
          style={{ width: '100%' }}
          rules={[{ required: true, message: '必填' }, { max: 64 }]}
        >
          <Input placeholder="如：武将" disabled={!canWrite} />
        </Form.Item>

        <Form.Item
          label="语义分类 semantic_type"
          name="semantic_type"
          rules={[{ required: true, message: '必选' }]}
        >
          <Select options={semanticTypeOptions} disabled={!canWrite} />
        </Form.Item>

        <Form.Item label="同义词 synonyms（点击添加）" name="synonyms">
          <Chips
            placeholder="输入后回车添加同义词，如 大将、将领、五虎将"
            style={{ width: '100%' }}
            size="large"
            variant="outlined"
            disabled={!canWrite}
          />
        </Form.Item>

        <Space.Compact style={{ width: '100%' }} direction="vertical" size="middle">
          <Form.Item label="近义词（逗号/顿号/换行分隔）" name="near_synonyms_text">
            <TextArea rows={2} placeholder="如 良将,名将" disabled={!canWrite} />
          </Form.Item>
          <Form.Item label="别名（逗号/顿号/换行分隔）" name="aliases_text">
            <TextArea rows={2} placeholder="如 关张赵马黄" disabled={!canWrite} />
          </Form.Item>
        </Space.Compact>

        <Form.Item label="停用词 Stoplist" name="stoplist" valuePropName="checked">
          <Space>
            <Switch disabled={!canWrite} />
            <Text type="secondary">
              加入停用词后，OL 流水线的 L1 对齐阶段将直接过滤该词，不再产出候选
            </Text>
          </Space>
        </Form.Item>
      </Form>
    </Modal>
  );
}
