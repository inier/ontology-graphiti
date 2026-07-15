/**
 * 语义域 Modal 表单：新建 / 编辑 / 查看
 * 字段：code / display_name / description / en_mapping JSON Editor
 */
import React, { useEffect, useMemo } from 'react';
import { Modal, Form, Input, App, Space, Alert, Typography } from 'antd';
import type { FormInstance } from 'antd';
import type { UslDomain, DomainPayload } from '../types';
import { createDomain, updateDomain, getDomain } from '../services/uslApi';
import { useUslPermissions } from '../hooks/useUslPermissions';

const { TextArea } = Input;
const { Text } = Typography;

export interface DomainFormValues {
  code: string;
  display_name: string;
  description?: string;
  /** JSON 字符串（表单层用文本，提交时 parse） */
  en_mapping_text?: string;
}

interface DomainFormProps {
  open: boolean;
  mode: 'create' | 'edit' | 'view';
  initial?: UslDomain;
  onCancel: () => void;
  onSubmitted: () => void;
}

function tryParseEnMapping(
  text: string | undefined,
): Record<string, string> | { _error: string } {
  if (!text || !text.trim()) return {};
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, string>;
    }
    return { _error: 'en_mapping 必须是 JSON Object（Key: 英文 PascalCase，Value: 中文）' };
  } catch (e) {
    return {
      _error: `JSON 解析失败：${e instanceof Error ? e.message : String(e)}`,
    };
  }
}

export function DomainForm({ open, mode, initial, onCancel, onSubmitted }: DomainFormProps) {
  const { message } = App.useApp();
  const { canWrite } = useUslPermissions();
  const [form] = Form.useForm<DomainFormValues>();
  const [submitting, setSubmitting] = React.useState(false);

  const readOnly = mode === 'view';

  useEffect(() => {
    if (!open) return;
    if (initial) {
      form.setFieldsValue({
        code: initial.code,
        display_name: initial.display_name,
        description: initial.description || '',
        en_mapping_text: initial.en_mapping
          ? JSON.stringify(initial.en_mapping, null, 2)
          : '',
      });
      // 编辑模式：如果 mode=edit 且有 initial，尝试重新拉取一次详情（确保最新）
      if (mode === 'edit') {
        void (async () => {
          try {
            const fresh = await getDomain(initial.code);
            form.setFieldsValue({
              code: fresh.code,
              display_name: fresh.display_name,
              description: fresh.description || '',
              en_mapping_text: fresh.en_mapping
                ? JSON.stringify(fresh.en_mapping, null, 2)
                : '',
            });
          } catch (e) {
            console.warn('[DomainForm] getDomain fallback', e);
          }
        })();
      }
    } else {
      form.resetFields();
    }
  }, [open, initial, mode, form]);

  const jsonError = useMemo(() => {
    const val = form.getFieldValue('en_mapping_text') as string | undefined;
    if (!val) return '';
    const parsed = tryParseEnMapping(val);
    return '_error' in parsed ? parsed._error : '';
  }, [form]);

  const handleOk = async () => {
    if (readOnly) {
      onCancel();
      return;
    }
    try {
      const values = await form.validateFields();
      const enMappingParsed = tryParseEnMapping(values.en_mapping_text);
      if ('_error' in enMappingParsed) {
        message.error(enMappingParsed._error);
        return;
      }
      const payload: DomainPayload = {
        code: values.code.trim(),
        display_name: values.display_name.trim(),
        description: values.description?.trim() || undefined,
        en_mapping: Object.keys(enMappingParsed).length > 0 ? enMappingParsed : undefined,
      };

      setSubmitting(true);
      if (mode === 'create') {
        const created = await createDomain(payload);
        message.success(`语义域 ${created.code} 创建成功`);
      } else if (mode === 'edit' && initial) {
        const updated = await updateDomain(initial.code, payload);
        message.success(`语义域 ${updated.code} 更新成功`);
      }
      onSubmitted();
    } catch (err) {
      // Form validateFields 错误已在 UI 展示，其他错误弹 message
      if (err instanceof Error && !String(err.message).includes('validate')) {
        message.error(err.message || '提交失败');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const titleMap: Record<string, string> = {
    create: '新建语义域',
    edit: `编辑语义域 ${initial?.code || ''}`,
    view: `查看语义域 ${initial?.code || ''}`,
  };

  return (
    <Modal
      title={titleMap[mode]}
      open={open}
      onCancel={onCancel}
      destroyOnHidden
      width={640}
      footer={(_, { OkBtn, CancelBtn }) => (
        <Space>
          <CancelBtn />
          {!readOnly && (
            <OkBtn disabled={!canWrite} loading={submitting} onClick={handleOk}>
              {mode === 'create' ? '创建' : '保存'}
            </OkBtn>
          )}
        </Space>
      )}
    >
      {readOnly && (
        <Alert type="info" showIcon message="只读模式：不允许修改" style={{ marginBottom: 16 }} />
      )}
      <Form
        form={form}
        layout="vertical"
        requiredMark="optional"
        preserve={false}
      >
        <Form.Item
          label="Code（唯一英文标识，如 sanguo_common）"
          name="code"
          rules={[
            { required: true, message: '必填' },
            { pattern: /^[a-z][a-z0-9_]*(-[a-z0-9_]+)*$/, message: '仅允许小写字母/数字/下划线，单词间可连字符' },
            { max: 64, message: '最长 64 字符' },
          ]}
        >
          <Input placeholder="sanguo_common" disabled={mode === 'edit' || readOnly} />
        </Form.Item>
        <Form.Item
          label="显示中文名"
          name="display_name"
          rules={[
            { required: true, message: '必填' },
            { min: 1, max: 64, message: '1~64 字符' },
          ]}
        >
          <Input placeholder="三国通用语域" disabled={readOnly} />
        </Form.Item>
        <Form.Item label="描述" name="description">
          <TextArea rows={2} placeholder="可选" disabled={readOnly} />
        </Form.Item>
        <Form.Item
          label={(
            <Space>
              <span>en_mapping（英文→中文映射，JSON Object）</span>
              <Text type="secondary" style={{ fontSize: 12 }}>
                例：{`{"Faction": "势力", "General": "武将"}`}
              </Text>
            </Space>
          )}
          name="en_mapping_text"
          validateStatus={jsonError ? 'error' : ''}
          help={jsonError || ''}
        >
          <TextArea
            rows={6}
            placeholder="{}"
            disabled={readOnly}
            style={{ fontFamily: 'Consolas, Monaco, monospace' }}
          />
        </Form.Item>
        {mode !== 'view' && !canWrite && (
          <Alert
            type="warning"
            showIcon
            message="您当前角色无写权限（需要 admin / schema_auditor），仅可查看"
          />
        )}
      </Form>
    </Modal>
  );
}

// 兼容 FormInstance 类型给外部使用（避免 TSC 未使用告警）
export type _DomainFormInstance = FormInstance<DomainFormValues>;
