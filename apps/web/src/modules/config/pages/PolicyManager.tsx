import { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  message,
  Badge,
  Empty,
  Popconfirm,
  Descriptions,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  ThunderboltOutlined,
  SafetyCertificateOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { PolicyEditor } from '../components/PolicyEditor';
import { AdvancedTable } from '@/modules/shared';

interface Policy {
  policy_id: string;
  name: string;
  description: string;
  category: string;
  compile_status: string;
  version: number;
  markdown_content?: string;
  rego_text?: string;
  created_at?: string;
  updated_at?: string;
  compile_errors?: string[];
}

const POLICY_CATEGORIES = [
  { value: 'access_control', label: 'Access Control' },
  { value: 'data_privacy', label: 'Data Privacy' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'security', label: 'Security' },
  { value: 'workflow', label: 'Workflow' },
  { value: 'custom', label: 'Custom' },
];

export function PolicyManager() {
  const { t } = useI18n('audit');

  const CATEGORY_LABELS: Record<string, string> = {
    access_control: t('访问控制'),
    data_privacy: t('数据隐私'),
    compliance: t('合规审计'),
    security: t('安全策略'),
    workflow: t('工作流控制'),
    custom: t('自定义'),
  };
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);
  const [editContent, setEditContent] = useState('');
  const [compileStatuses, setCompileStatuses] = useState<
    Record<string, { status: string; errors?: string[] }>
  >({});
  const [createForm] = Form.useForm();

  const fetchPolicies = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ policies: Policy[] }>('/api/policies?limit=100');
      setPolicies(data.policies || []);
    } catch {
      message.error('Failed to load policies');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  const handleCreate = async (values: {
    name: string;
    description: string;
    category: string;
    markdown_content: string;
  }) => {
    try {
      await apiClient.post('/api/policy/markdown', values);
      message.success(t('创建策略') + ' success');
      setCreateModalOpen(false);
      createForm.resetFields();
      fetchPolicies();
    } catch (error) {
      message.error(`Create failed: ${error}`);
    }
  };

  const handleCompile = async (policyId: string) => {
    try {
      const result = await apiClient.post<{
        compile_status: string;
        errors?: string[];
      }>(`/api/policy/markdown/${policyId}/compile`);
      setCompileStatuses((prev) => ({
        ...prev,
        [policyId]: {
          status: result.compile_status,
          errors: result.errors,
        },
      }));
      message.success(
        result.compile_status === 'compiled'
          ? t('编译成功')
          : t('编译失败')
      );
    } catch (error) {
      setCompileStatuses((prev) => ({
        ...prev,
        [policyId]: { status: 'error', errors: [String(error)] },
      }));
      message.error(t('编译失败'));
    }
  };

  const handleHotUpdate = async (policyId: string, markdownContent: string) => {
    try {
      await apiClient.put(`/api/policy/markdown/${policyId}`, {
        markdown_content: markdownContent,
      });
      message.success(t('热更新') + ' success');
      fetchPolicies();
    } catch (error) {
      message.error(`Hot update failed: ${error}`);
    }
  };

  const handleDelete = async (policyId: string) => {
    try {
      await apiClient.delete(`/api/policies/${policyId}`);
      message.success('Policy deleted');
      fetchPolicies();
    } catch (error) {
      message.error(`Delete failed: ${error}`);
    }
  };

  const handleEditOpen = (policy: Policy) => {
    setSelectedPolicy(policy);
    setEditContent(policy.markdown_content || '');
    setEditModalOpen(true);
  };

  const handleEditSave = async () => {
    if (!selectedPolicy) return;
    await handleHotUpdate(selectedPolicy.policy_id, editContent);
    setEditModalOpen(false);
    setSelectedPolicy(null);
    setEditContent('');
  };

  const getCompileStatusTag = (policy: Policy) => {
    const status = compileStatuses[policy.policy_id]?.status || policy.compile_status;
    if (status === 'compiled' || status === 'success') {
      return (
        <Tag icon={<CheckCircleOutlined />} color="success">
          {t('编译成功')}
        </Tag>
      );
    }
    if (status === 'error' || status === 'failed') {
      return (
        <Tag icon={<CloseCircleOutlined />} color="error">
          {t('编译失败')}
        </Tag>
      );
    }
    return <Tag color="processing">{status || 'pending'}</Tag>;
  };

  const columns = [
    {
      title: t('策略名称'),
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: Policy) => (
        <Space>
          <SafetyCertificateOutlined style={{ color: '#1890ff' }} />
          <a onClick={() => handleEditOpen(record)}>{name}</a>
        </Space>
      ),
    },
    {
      title: t('策略分类'),
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (cat: string) => (
        <Tag color="blue">{CATEGORY_LABELS[cat] || cat}</Tag>
      ),
    },
    {
      title: t('编译状态'),
      key: 'compile_status',
      width: 140,
      render: (_: unknown, record: Policy) => getCompileStatusTag(record),
    },
    {
      title: t('版本'),
      dataIndex: 'version',
      key: 'version',
      width: 80,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 200,
      render: (_: unknown, record: Policy) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<ThunderboltOutlined />}
            onClick={() => handleCompile(record.policy_id)}
          >
            {t('编译')}
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditOpen(record)}
          >
            {t('编辑策略')}
          </Button>
          <Popconfirm
            title="Confirm delete this policy?"
            onConfirm={() => handleDelete(record.policy_id)}
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title={
          <Space>
            <SafetyCertificateOutlined />
            <span>{t('OPA 策略管理')}</span>
            <Badge count={policies.length} style={{ backgroundColor: '#1890ff' }} />
          </Space>
        }
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchPolicies}>
              Refresh
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalOpen(true)}
            >
              {t('创建策略')}
            </Button>
          </Space>
        }
      >
        <AdvancedTable
          columns={columns}
          dataSource={policies}
          rowKey="policy_id"
          loading={loading}
          pagination={{ pageSize: 10 }}
          locale={{
            emptyText: <Empty description="No policies yet" />,
          }}
        />
      </Card>

      <Modal
        title={t('创建策略')}
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onOk={() => createForm.submit()}
        okText={t('创建策略')}
        width={800}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="name"
            label={t('策略名称')}
            rules={[{ required: true, message: 'Please enter policy name' }]}
          >
            <Input placeholder="e.g. Analyst Access Control Policy" />
          </Form.Item>
          <Form.Item
            name="category"
            label={t('策略分类')}
            rules={[{ required: true, message: 'Please select category' }]}
            initialValue="access_control"
          >
            <Select>
              {POLICY_CATEGORIES.map((cat) => (
                <Select.Option key={cat.value} value={cat.value}>
                  {cat.label}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="description"
            label={t('策略描述')}
            rules={[{ required: true, message: 'Please enter description' }]}
          >
            <Input.TextArea rows={2} placeholder="Brief description of the policy" />
          </Form.Item>
          <Form.Item
            name="markdown_content"
            label={t('策略内容')}
            rules={[{ required: true, message: 'Please enter policy content' }]}
          >
            <PolicyEditor
              compileStatus={
                selectedPolicy
                  ? compileStatuses[selectedPolicy.policy_id]
                  : undefined
              }
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`${t('编辑策略')} — ${selectedPolicy?.name || ''}`}
        open={editModalOpen}
        onCancel={() => {
          setEditModalOpen(false);
          setSelectedPolicy(null);
          setEditContent('');
        }}
        onOk={handleEditSave}
        okText={t('热更新')}
        width={800}
      >
        {selectedPolicy && (
          <>
            <Descriptions column={2} style={{ marginBottom: 16 }}>
              <Descriptions.Item label={t('策略名称')}>
                {selectedPolicy.name}
              </Descriptions.Item>
              <Descriptions.Item label={t('策略分类')}>
                <Tag color="blue">
                  {CATEGORY_LABELS[selectedPolicy.category] || selectedPolicy.category}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('版本')}>
                {selectedPolicy.version}
              </Descriptions.Item>
              <Descriptions.Item label={t('编译状态')}>
                {getCompileStatusTag(selectedPolicy)}
              </Descriptions.Item>
            </Descriptions>
            <PolicyEditor
              value={editContent}
              onChange={setEditContent}
              compileStatus={compileStatuses[selectedPolicy.policy_id]}
            />
          </>
        )}
      </Modal>
    </div>
  );
}
