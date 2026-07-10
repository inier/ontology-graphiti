import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Button, Modal, Form, Select, Input, Tag, Space,
  Descriptions, Badge, message, Tooltip, Drawer,
} from 'antd';
import {
  ThunderboltOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ClockCircleOutlined, ExclamationCircleOutlined, SyncOutlined,
} from '@ant-design/icons';
import { api } from '@/modules/shared/services/api';
import { AdvancedTable } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const STATUS_ICONS: Record<string, { color: string; icon: React.ReactNode }> = {
  pending: { color: 'default', icon: <ClockCircleOutlined /> },
  validating: { color: 'processing', icon: <SyncOutlined spin /> },
  approved: { color: 'blue', icon: <CheckCircleOutlined /> },
  rejected: { color: 'red', icon: <CloseCircleOutlined /> },
  executing: { color: 'processing', icon: <SyncOutlined spin /> },
  completed: { color: 'success', icon: <CheckCircleOutlined /> },
  failed: { color: 'error', icon: <CloseCircleOutlined /> },
  rolled_back: { color: 'warning', icon: <ExclamationCircleOutlined /> },
};

const ActionPanel: React.FC = () => {
  const { t } = useI18n('ontology');
  const [records, setRecords] = useState<any[]>([]);
  const [actionTypes, setActionTypes] = useState<any[]>([]);
  const [objectTypes, setObjectTypes] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitOpen, setSubmitOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [currentRecord, setCurrentRecord] = useState<any>(null);
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

  const loadObjectTypes = useCallback(async () => {
    try {
      const data = await api.listObjectTypes();
      setObjectTypes(Array.isArray(data) ? data : []);
    } catch {
      setObjectTypes([]);
    }
  }, []);

  useEffect(() => {
    loadRecords();
    loadActionTypes();
    loadObjectTypes();
  }, [loadRecords, loadActionTypes, loadObjectTypes]);

  const handleSubmit = async (values: any) => {
    try {
      const selectedAction = actionTypes.find(a => a.action_type_id === values.action_type_id);
      await api.submitAction({
        action_type_id: values.action_type_id,
        target_object_id: values.target_object_id,
        target_object_type: selectedAction?.target_object_type || 'Unit',
        parameters: values.parameters ? JSON.parse(values.parameters) : {},
        requested_by: values.requested_by || 'user',
        reason: values.reason || '',
      });
      message.success(t('actionPanel.submitted'));
      setSubmitOpen(false);
      form.resetFields();
      loadRecords();
    } catch (e: any) {
      message.error(e?.message || t('actionPanel.submitFailed'));
    }
  };

  const handleApprove = async (recordId: string, approved: boolean) => {
    try {
      await api.approveAction(recordId, {
        approved,
        approver: 'user',
        comment: approved ? t('actionPanel.approved') : t('actionPanel.rejected'),
      });
      message.success(approved ? t('actionPanel.approved') : t('actionPanel.rejected'));
      loadRecords();
      setDetailOpen(false);
    } catch (e: any) {
      message.error(e?.message || t('actionPanel.operationFailed'));
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'action_record_id',
      key: 'id',
      width: 140,
      render: (id: string) => <a onClick={() => { setCurrentRecord(records.find(r => r.action_record_id === id)); setDetailOpen(true); }}>{id.slice(0, 16)}…</a>,
    },
    {
      title: t('actionPanel.actionType'),
      dataIndex: 'action_type_id',
      key: 'type',
      width: 100,
      render: (t: string) => <Tag color="blue">{t}</Tag>,
    },
    {
      title: t('actionPanel.targetObject'),
      dataIndex: 'target_object_id',
      key: 'target',
      width: 120,
      ellipsis: true,
    },
    {
      title: t('actionPanel.targetType'),
      dataIndex: 'target_object_type',
      key: 'target_type',
      width: 90,
    },
    {
      title: t('common.label.status'),
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const cfg = STATUS_ICONS[status] || { color: 'default', icon: null };
        const label = t(`actionPanel.statuses.${status}`, status);
        return <Tag icon={cfg.icon} color={cfg.color}>{label}</Tag>;
      },
    },
    {
      title: t('actionPanel.requester'),
      dataIndex: 'requested_by',
      key: 'by',
      width: 80,
    },
    {
      title: t('actionPanel.time'),
      dataIndex: 'created_at',
      key: 'time',
      width: 160,
      render: (t: string) => t ? new Date(t).toLocaleString() : '-',
    },
    {
      title: t('common.label.actions'),
      key: 'action',
      width: 100,
      render: (_: any, record: any) => {
        if (record.status === 'approved') {
          return (
            <Button size="small" type="primary" onClick={() => handleApprove(record.action_record_id, true)}>
              {t('actionPanel.execute')}
            </Button>
          );
        }
        if (record.status === 'pending') {
          return (
            <Space size="small">
              <Button size="small" type="primary" onClick={() => handleApprove(record.action_record_id, true)}>{t('actionPanel.approve')}</Button>
              <Button size="small" danger onClick={() => handleApprove(record.action_record_id, false)}>{t('actionPanel.reject')}</Button>
            </Space>
          );
        }
        return null;
      },
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card
        title={<Space><ThunderboltOutlined />{t('actionPanel.title')}</Space>}
        styles={{ body: { padding: 16 } }}
        extra={
          <Space>
            <Select
              placeholder={t('actionPanel.filterPlaceholder')}
              allowClear
              style={{ width: 120 }}
              value={statusFilter}
              onChange={setStatusFilter}
            >
              {Object.entries(STATUS_ICONS).map(([k]) => (
                <Select.Option key={k} value={k}>{t(`actionPanel.statuses.${k}`, k)}</Select.Option>
              ))}
            </Select>
            <Button type="primary" icon={<ThunderboltOutlined />} onClick={() => setSubmitOpen(true)}>
              {t('actionPanel.submitAction')}
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
        title={t('actionPanel.submitAction')}
        open={submitOpen}
        onCancel={() => { setSubmitOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="action_type_id" label={t('actionPanel.actionType')} rules={[{ required: true, message: t('actionPanel.selectActionType') }]}>
            <Select placeholder={t('actionPanel.selectActionType')}>
              {actionTypes.map(a => (
                <Select.Option key={a.action_type_id} value={a.action_type_id}>
                  {a.display_name || a.name} → {a.target_object_type}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="target_object_id" label={t('actionPanel.targetObjectId')} rules={[{ required: true, message: t('actionPanel.enterTargetId') }]}>
            <Input placeholder={t('actionPanel.enterTargetId')} />
          </Form.Item>
          <Form.Item name="parameters" label={t('actionPanel.parameters')}>
            <Input.TextArea rows={3} placeholder={t('actionPanel.parametersPlaceholder')} />
          </Form.Item>
          <Form.Item name="reason" label={t('actionPanel.reason')}>
            <Input.TextArea rows={2} placeholder={t('actionPanel.executeReason')} />
          </Form.Item>
          <Form.Item name="requested_by" label={t('actionPanel.requester')}>
            <Input placeholder={t('actionPanel.defaultUser')} />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title={t('actionPanel.actionDetail')}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        width={520}
      >
        {currentRecord && (
          <Descriptions column={1}>
            <Descriptions.Item label={t('actionPanel.recordId')}>{currentRecord.action_record_id}</Descriptions.Item>
            <Descriptions.Item label={t('actionPanel.actionType')}>
              <Tag color="blue">{currentRecord.action_type_id}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('actionPanel.targetObject')}>{currentRecord.target_object_id}</Descriptions.Item>
            <Descriptions.Item label={t('actionPanel.targetType')}>{currentRecord.target_object_type}</Descriptions.Item>
            <Descriptions.Item label={t('common.label.status')}>
              {(() => {
                const cfg = STATUS_ICONS[currentRecord.status] || { color: 'default', icon: null };
                const label = t(`actionPanel.statuses.${currentRecord.status}`, currentRecord.status);
                return <Badge status={cfg.color as any} text={label} />;
              })()}
            </Descriptions.Item>
            <Descriptions.Item label={t('actionPanel.requester')}>{currentRecord.requested_by}</Descriptions.Item>
            <Descriptions.Item label={t('actionPanel.reason')}>{currentRecord.reason || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('actionPanel.parameters')}>
              <pre style={{ margin: 0, fontSize: 12 }}>
                {JSON.stringify(currentRecord.parameters, null, 2)}
              </pre>
            </Descriptions.Item>
            {currentRecord.opa_decision && (
              <Descriptions.Item label={t('actionPanel.opaDecision')}>
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(currentRecord.opa_decision, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
            {currentRecord.execution_result && (
              <Descriptions.Item label={t('actionPanel.execResult')}>
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(currentRecord.execution_result, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
            {currentRecord.writeback_result && (
              <Descriptions.Item label={t('actionPanel.writebackResult')}>
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(currentRecord.writeback_result, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
            <Descriptions.Item label={t('actionPanel.createdAt')}>
              {currentRecord.created_at ? new Date(currentRecord.created_at).toLocaleString() : '-'}
            </Descriptions.Item>
            <Descriptions.Item label={t('actionPanel.updatedAt')}>
              {currentRecord.updated_at ? new Date(currentRecord.updated_at).toLocaleString() : '-'}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
};

export default ActionPanel;
