import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Button, Modal, Form, Input, Select, Tag,
  Card, Space, Typography, Descriptions, message, Popconfirm, Empty,
} from 'antd';
import {
  PlusOutlined, PlayCircleOutlined, StopOutlined, DeleteOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { AdvancedTable, wrapRequest } from '@/modules/shared';
import type { ActionType } from '@ant-design/pro-components';

const { Text } = Typography;

interface SandboxRecord {
  sandbox_id: string;
  name: string;
  description: string;
  ontology_id: string;
  status: 'created' | 'running' | 'stopped' | 'error' | 'destroyed';
  created_at: string;
  config: Record<string, unknown>;
}

interface SandboxResult {
  status: string;
  sandbox_id: string;
  metric_changes: Array<{
    metric_name: string;
    before: unknown;
    after: unknown;
    delta: number | null;
  }>;
  risk_assessment: Record<string, unknown>;
  recommendation: string;
  confidence: number;
}

const STATUS_COLORS: Record<string, string> = {
  created: 'default',
  running: 'processing',
  stopped: 'orange',
  error: 'red',
  destroyed: 'default',
};

const SandboxManager: React.FC = () => {
  const { t } = useI18n();
  const actionRef = useRef<ActionType>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [resultOpen, setResultOpen] = useState(false);
  const [currentResult, setCurrentResult] = useState<SandboxResult | null>(null);
  const [ontologies, setOntologies] = useState<Array<{ id: string; name: string }>>([]);
  const [form] = Form.useForm();

  const fetchSandboxList = async (): Promise<SandboxRecord[]> => {
    const data = await apiClient.get<{ sandboxes: SandboxRecord[] }>('/api/simulation/sandbox');
    return data.sandboxes || [];
  };

  const request = wrapRequest(fetchSandboxList);

  const fetchOntologies = useCallback(async () => {
    try {
      const data = await apiClient.get<{ ontologies: Array<{ id: string; name: string }> }>('/api/ontology');
      setOntologies(data.ontologies || []);
    } catch {
      setOntologies([]);
    }
  }, []);

  useEffect(() => {
    fetchOntologies();
  }, [fetchOntologies]);

  const handleCreate = async (values: Record<string, unknown>) => {
    try {
      await apiClient.post('/api/simulation/sandbox', {
        name: values.name,
        description: values.description,
        ontology_id: values.ontology_id,
      });
      message.success(t('沙箱创建成功'));
      setCreateOpen(false);
      form.resetFields();
      actionRef.current?.reload();
    } catch (e) {
      message.error(`${t('创建失败')}: ${(e as Error).message}`);
    }
  };

  const handleRun = async (sandboxId: string) => {
    try {
      await apiClient.post(`/api/simulation/sandbox/${sandboxId}/run`, {});
      message.success(t('沙箱已启动'));
      actionRef.current?.reload();
    } catch (e) {
      message.error(`${t('运行失败')}: ${(e as Error).message}`);
    }
  };

  const handleStop = async (sandboxId: string) => {
    try {
      await apiClient.post(`/api/simulation/sandbox/${sandboxId}/stop`, {});
      message.success(t('沙箱已停止'));
      actionRef.current?.reload();
    } catch (e) {
      message.error(`${t('停止失败')}: ${(e as Error).message}`);
    }
  };

  const handleDestroy = async (sandboxId: string) => {
    try {
      await apiClient.delete(`/api/simulation/sandbox/${sandboxId}`);
      message.success(t('沙箱已销毁'));
      actionRef.current?.reload();
    } catch (e) {
      message.error(`${t('销毁失败')}: ${(e as Error).message}`);
    }
  };

  const handleViewResults = async (sandboxId: string) => {
    try {
      const data = await apiClient.get<SandboxResult>(`/api/simulation/sandbox/${sandboxId}/results`);
      setCurrentResult(data);
      setResultOpen(true);
    } catch (e) {
      message.error(`${t('加载结果失败')}: ${(e as Error).message}`);
    }
  };

  const columns: ColumnsType<SandboxRecord> = [
    {
      title: t('名称'),
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: t('状态'),
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={STATUS_COLORS[status] || 'default'}>{status}</Tag>
      ),
    },
    {
      title: t('本体'),
      dataIndex: 'ontology_id',
      key: 'ontology_id',
      width: 140,
      ellipsis: true,
    },
    {
      title: t('创建时间'),
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      ellipsis: true,
    },
    {
      title: t('操作'),
      key: 'actions',
      width: 220,
      render: (_: unknown, record: SandboxRecord) => (
        <Space size="small">
          {record.status === 'created' || record.status === 'stopped' ? (
            <Button
              type="primary"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => handleRun(record.sandbox_id)}
            >
              {t('运行')}
            </Button>
          ) : null}
          {record.status === 'running' ? (
            <Button
              size="small"
              icon={<StopOutlined />}
              onClick={() => handleStop(record.sandbox_id)}
            >
              {t('停止')}
            </Button>
          ) : null}
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewResults(record.sandbox_id)}
            disabled={record.status === 'created' || record.status === 'destroyed'}
          >
            {t('结果')}
          </Button>
          <Popconfirm
            title={t('确认销毁此沙箱？')}
            onConfirm={() => handleDestroy(record.sandbox_id)}
          >
            <Button type="text" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title={t('沙箱管理')}
        extra={
          <Space>
            <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              {t('创建沙箱')}
            </Button>
          </Space>
        }
      >
        <AdvancedTable
          request={request}
          actionRef={actionRef}
          columns={columns}
          rowKey="sandbox_id"
          size="small"
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: <Empty description={t('暂无沙箱')} image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        />
      </Card>

      <Modal
        title={t('创建沙箱')}
        open={createOpen}
        onCancel={() => { setCreateOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label={t('名称')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label={t('描述')}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="ontology_id" label={t('本体绑定')} rules={[{ required: true }]}>
            <Select
              placeholder={t('请选择本体')}
              options={ontologies.map(o => ({ value: o.id, label: o.name }))}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={t('沙箱结果')}
        open={resultOpen}
        onCancel={() => { setResultOpen(false); setCurrentResult(null); }}
        footer={null}
        width={720}
      >
        {currentResult ? (
          <Space orientation="vertical" style={{ width: '100%' }} size="middle">
            <Descriptions column={2}>
              <Descriptions.Item label={t('沙箱 ID')}>{currentResult.sandbox_id}</Descriptions.Item>
              <Descriptions.Item label={t('状态')}>
                <Tag color={currentResult.status === 'completed' ? 'green' : 'red'}>{currentResult.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('置信度')}>
                <Text>{(currentResult.confidence * 100).toFixed(1)}%</Text>
              </Descriptions.Item>
            </Descriptions>
            {currentResult.metric_changes && currentResult.metric_changes.length > 0 && (
              <Card title={t('指标变化')} size="small">
                <AdvancedTable
                  dataSource={currentResult.metric_changes}
                  columns={[
                    { title: t('指标'), dataIndex: 'metric_name', key: 'metric_name' },
                    { title: t('变化前'), dataIndex: 'before', key: 'before' },
                    { title: t('变化后'), dataIndex: 'after', key: 'after' },
                    {
                      title: t('变化量'),
                      dataIndex: 'delta',
                      key: 'delta',
                      render: (v: number | null) => v != null ? (
                        <Text style={{ color: v >= 0 ? '#52c41a' : '#ff4d4f' }}>
                          {v >= 0 ? '+' : ''}{v.toFixed(3)}
                        </Text>
                      ) : '-',
                    },
                  ]}
                  rowKey="metric_name"
                  size="small"
                  pagination={false}
                />
              </Card>
            )}
            {currentResult.recommendation && (
              <Card size="small">
                <Text strong>{t('推荐')}: </Text>
                <Text>{currentResult.recommendation}</Text>
              </Card>
            )}
          </Space>
        ) : (
          <Empty description={t('暂无结果')} />
        )}
      </Modal>
    </>
  );
};

export default SandboxManager;
