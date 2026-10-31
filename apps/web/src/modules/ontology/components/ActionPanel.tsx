import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Button, Modal, Form, Select, Input, Tag, Space,
  Descriptions, Badge, message, Drawer, Typography,
} from 'antd';
import {
  ThunderboltOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ClockCircleOutlined, ExclamationCircleOutlined, SyncOutlined,
} from '@ant-design/icons';
import { api } from '@/modules/shared/services/api';
import type { ActionRecordRow, OmsActionType } from '@/modules/shared/services/api';
import { AdvancedTable } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';

/**
 * 状态与后端 ActionRequestStatus 一一对应（odap/biz/decision/action_service/schemas.py）。
 *
 * 关键语义：`pending → validating → approved|rejected` 由后端在 submit 时依据 OPA 策略
 * **自动裁决**，不存在人工"批准/拒绝"接口；`POST /api/actions/{id}/approve` 的语义是
 * **批准并执行**，且只接受已处于 `approved` 状态的记录（executor.approve_and_execute）。
 * 因此前端只在 `approved` 上给「执行」按钮，其余状态只读。
 */
const STATUS_META: Record<
  string,
  { color: 'default' | 'processing' | 'success' | 'error' | 'warning'; icon: React.ReactNode; label: string }
> = {
  pending: { color: 'default', icon: <ClockCircleOutlined />, label: '待策略裁决' },
  validating: { color: 'processing', icon: <SyncOutlined spin />, label: '校验中' },
  approved: { color: 'processing', icon: <CheckCircleOutlined />, label: '待执行' },
  rejected: { color: 'error', icon: <CloseCircleOutlined />, label: '策略已拒绝' },
  executing: { color: 'processing', icon: <SyncOutlined spin />, label: '执行中' },
  completed: { color: 'success', icon: <CheckCircleOutlined />, label: '已完成' },
  failed: { color: 'error', icon: <CloseCircleOutlined />, label: '执行失败' },
  rolled_back: { color: 'warning', icon: <ExclamationCircleOutlined />, label: '已回滚' },
};

const { Text } = Typography;

/** 提交动作表单的字段（parameters 在表单里是 JSON 文本，提交前解析） */
interface SubmitActionFormValues {
  action_type_id: string;
  target_object_id: string;
  parameters?: string;
  requested_by?: string;
  reason?: string;
}

const ActionPanel: React.FC = () => {
  const { t } = useI18n('ontology');
  const [records, setRecords] = useState<ActionRecordRow[]>([]);
  const [actionTypes, setActionTypes] = useState<OmsActionType[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitOpen, setSubmitOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [currentRecord, setCurrentRecord] = useState<ActionRecordRow | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [form] = Form.useForm();

  const loadRecords = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listActionRecords(statusFilter, 50, 0);
      setRecords(Array.isArray(data) ? data : []);
    } catch {
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  const loadActionTypes = useCallback(async () => {
    try {
      const data = await api.listActionTypes();
      setActionTypes(Array.isArray(data) ? data : []);
    } catch {
      setActionTypes([]);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      loadRecords();
    })();
    void (async () => {
      loadActionTypes();
    })();
  }, [loadRecords, loadActionTypes]);

  const handleSubmit = async (values: SubmitActionFormValues) => {
    const selectedAction = actionTypes.find((a) => a.action_type_id === values.action_type_id);
    // 目标类型来自动作类型定义（OmsActionType.target_type），不再用魔法兜底
    const targetObjectType = selectedAction?.target_type;
    if (!targetObjectType) {
      message.error(t('所选动作类型缺少目标类型定义，无法提交'));
      return;
    }
    let parameters: Record<string, unknown> = {};
    if (values.parameters) {
      try {
        const parsed: unknown = JSON.parse(values.parameters);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          message.error(t('参数必须是 JSON 对象'));
          return;
        }
        parameters = parsed as Record<string, unknown>;
      } catch (e) {
        message.error(`${t('参数不是合法 JSON')}: ${e instanceof Error ? e.message : String(e)}`);
        return;
      }
    }
    try {
      await api.submitAction({
        action_type_id: values.action_type_id,
        target_object_id: values.target_object_id,
        target_object_type: targetObjectType,
        parameters,
        requested_by: values.requested_by || 'user',
        reason: values.reason || '',
      });
      message.success(t('动作已提交'));
      setSubmitOpen(false);
      form.resetFields();
      void loadRecords();
    } catch (e) {
      const errMessage = e instanceof Error ? e.message : String(e);
      message.error(errMessage || t('提交失败'));
    }
  };

  /** 后端 `/{id}/approve` = 批准并执行，仅对 approved 记录有效 */
  const handleExecute = async (recordId: string) => {
    try {
      await api.approveAction(recordId, {
        approved: true,
        approver: 'user',
        comment: t('在前端触发执行'),
      });
      message.success(t('已触发执行'));
      void loadRecords();
      setDetailOpen(false);
    } catch (e: unknown) {
      const errMessage = e instanceof Error ? e.message : String(e);
      message.error(errMessage || t('操作失败'));
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'action_record_id',
      key: 'id',
      width: 140,
      render: (id: string) => <a onClick={() => { setCurrentRecord(records.find(r => r.action_record_id === id) ?? null); setDetailOpen(true); }}>{id.slice(0, 16)}…</a>,
    },
    {
      title: t('动作类型'),
      dataIndex: 'action_type_id',
      key: 'type',
      width: 100,
      render: (t: string) => <Tag color="blue">{t}</Tag>,
    },
    {
      title: t('目标对象'),
      dataIndex: 'target_object_id',
      key: 'target',
      width: 120,
      ellipsis: true,
    },
    {
      title: t('目标类型'),
      dataIndex: 'target_object_type',
      key: 'target_type',
      width: 90,
    },
    {
      title: t('状态'),
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const meta = STATUS_META[status];
        return <Tag icon={meta?.icon} color={meta?.color ?? 'default'}>{meta ? t(meta.label) : status}</Tag>;
      },
    },
    {
      title: t('请求者'),
      dataIndex: 'requested_by',
      key: 'by',
      width: 80,
    },
    {
      title: t('时间'),
      dataIndex: 'created_at',
      key: 'time',
      width: 160,
      render: (t: string) => t ? new Date(t).toLocaleString() : '-',
    },
    {
      title: t('操作'),
      key: 'action',
      width: 100,
      render: (_: unknown, record: ActionRecordRow) => {
        // 只有 approved（策略放行后待执行）可触发执行；pending/validating 由后端自动裁决
        if (record.status === 'approved') {
          return (
            <Button size="small" type="primary" onClick={() => void handleExecute(record.action_record_id)}>
              {t('执行')}
            </Button>
          );
        }
        return <Text type="secondary">{t('无需操作')}</Text>;
      },
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card
        title={<Space><ThunderboltOutlined />{t('动作管理')}</Space>}
        styles={{ body: { padding: 16 } }}
        extra={
          <Space>
            <Select
              placeholder={t('状态筛选')}
              allowClear
              style={{ width: 120 }}
              value={statusFilter}
              onChange={setStatusFilter}
            >
              {Object.entries(STATUS_META).map(([k, meta]) => (
                <Select.Option key={k} value={k}>{t(meta.label)}</Select.Option>
              ))}
            </Select>
            <Button type="primary" icon={<ThunderboltOutlined />} onClick={() => setSubmitOpen(true)}>
              {t('提交动作')}
            </Button>
          </Space>
        }
      >
        <AdvancedTable
          columns={columns}
          dataSource={records}
          rowKey="action_record_id"
          loading={loading}
          size="small"
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <Modal
        title={t('提交动作')}
        open={submitOpen}
        onCancel={() => { setSubmitOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="action_type_id" label={t('动作类型')} rules={[{ required: true, message: t('选择动作类型') }]}>
            <Select placeholder={t('选择动作类型')}>
              {actionTypes.map(a => (
                <Select.Option key={a.action_type_id} value={a.action_type_id}>
                  {a.display_name || a.name} → {a.target_type}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="target_object_id" label={t('目标对象ID')} rules={[{ required: true, message: t('输入目标对象的唯一标识') }]}>
            <Input placeholder={t('输入目标对象的唯一标识')} />
          </Form.Item>
          <Form.Item name="parameters" label={t('参数')}>
            <Input.TextArea rows={3} placeholder={t('{"destination": "A区", "speed": 50}')} />
          </Form.Item>
          <Form.Item name="reason" label={t('原因')}>
            <Input.TextArea rows={2} placeholder={t('执行此动作的原因')} />
          </Form.Item>
          <Form.Item name="requested_by" label={t('请求者')}>
            <Input placeholder={t('默认: user')} />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title={t('动作详情')}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        width={520}
      >
        {currentRecord && (
          <Descriptions column={1}>
            <Descriptions.Item label={t('记录ID')}>{currentRecord.action_record_id}</Descriptions.Item>
            <Descriptions.Item label={t('动作类型')}>
              <Tag color="blue">{currentRecord.action_type_id}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('目标对象')}>{currentRecord.target_object_id}</Descriptions.Item>
            <Descriptions.Item label={t('目标类型')}>{currentRecord.target_object_type}</Descriptions.Item>
            <Descriptions.Item label={t('状态')}>
              {(() => {
                const meta = STATUS_META[currentRecord.status];
                // Badge 只接受 success/processing/error/warning/default 之一，映射后传入
                const badgeStatus = (meta?.color ?? 'default') as 'success' | 'processing' | 'error' | 'warning' | 'default';
                return <Badge status={badgeStatus} text={meta ? t(meta.label) : currentRecord.status} />;
              })()}
            </Descriptions.Item>
            <Descriptions.Item label={t('请求者')}>{currentRecord.requested_by}</Descriptions.Item>
            <Descriptions.Item label={t('原因')}>{currentRecord.reason || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('参数')}>
              <pre style={{ margin: 0, fontSize: 12 }}>
                {JSON.stringify(currentRecord.parameters, null, 2)}
              </pre>
            </Descriptions.Item>
            {currentRecord.opa_decision && (
              <Descriptions.Item label={t('OPA 决策')}>
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(currentRecord.opa_decision, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
            {currentRecord.execution_result && (
              <Descriptions.Item label={t('执行结果')}>
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(currentRecord.execution_result, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
            {currentRecord.writeback_result && (
              <Descriptions.Item label={t('写回结果')}>
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(currentRecord.writeback_result, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
            <Descriptions.Item label={t('创建时间')}>
              {currentRecord.created_at ? new Date(currentRecord.created_at).toLocaleString() : '-'}
            </Descriptions.Item>
            <Descriptions.Item label={t('更新时间')}>
              {currentRecord.updated_at ? new Date(currentRecord.updated_at).toLocaleString() : '-'}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
};

export default ActionPanel;
