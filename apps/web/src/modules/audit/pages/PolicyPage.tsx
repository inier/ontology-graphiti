import React, { useState, useEffect, useCallback } from 'react';
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
  Tooltip,
  Empty,
  Divider,
  Switch,
  Tabs,
  Timeline,
  Row,
  Col,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  EyeOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SafetyCertificateOutlined,
  CodeOutlined,
  ThunderboltOutlined,
  HistoryOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { useAuditStore } from '../stores/auditStore';
import type { ColumnsType } from 'antd/es/table';
import { AdvancedTable } from '@/modules/shared';

const { TextArea } = Input;

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
  'access_control',
  'data_privacy',
  'compliance',
  'security',
  'workflow',
  'custom',
];

const getCategoryLabel = (cat: string) => {
  const labels: Record<string, string> = {
    access_control: '访问控制',
    data_privacy: '数据隐私',
    compliance: '合规审计',
    security: '安全策略',
    workflow: '工作流控制',
    custom: '自定义',
  };
  return labels[cat] || cat;
};

const PolicyPage: React.FC = () => {
  const {
    policies,
    policyVersions,
    compileStatus,
    loading,
    loadPolicies,
    loadPolicyVersions,
    savePolicy,
    compilePolicy,
    hotUpdate,
    getCompileStatus,
  } = useAuditStore();

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [versionModalOpen, setVersionModalOpen] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);

  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  useEffect(() => {
    loadPolicies();
  }, [loadPolicies]);

  const handleCreate = async (values: Record<string, unknown>) => {
    const result = await savePolicy({
      name: values.name as string,
      description: values.description as string,
      markdown_content: values.markdown_content as string,
      category: values.category as string,
    });
    if (result) {
      message.success('策略创建成功');
      setCreateModalOpen(false);
      createForm.resetFields();
    }
  };

  const handleCompile = async (policyId: string) => {
    await compilePolicy(policyId);
    const status = useAuditStore.getState().compileStatus[policyId];
    if (status?.status === 'success') {
      message.success('编译成功');
    } else {
      message.error(`编译失败: ${status?.errors?.join(', ') || '未知错误'}`);
    }
  };

  const handleHotUpdate = async (policyId: string, markdownContent: string) => {
    try {
      await hotUpdate(policyId, markdownContent);
      message.success('热更新完成');
    } catch (error) {
      message.error(`热更新失败: ${error}`);
    }
  };

  const handleViewVersions = async (policy: Policy) => {
    setSelectedPolicy(policy);
    await loadPolicyVersions(policy.policy_id);
    setVersionModalOpen(true);
  };

  const handleEditOpen = (policy: Policy) => {
    setSelectedPolicy(policy);
    editForm.setFieldsValue({
      name: policy.name,
      description: policy.description,
      markdown_content: policy.markdown_content,
    });
    setEditModalOpen(true);
  };

  const handleEditSave = async (values: Record<string, unknown>) => {
    if (!selectedPolicy) return;
    await hotUpdate(selectedPolicy.policy_id, values.markdown_content as string);
    setEditModalOpen(false);
    editForm.resetFields();
  };

  const policyColumns: ColumnsType<Policy> = [
    {
      title: '策略名称',
      dataIndex: 'name',
      key: 'name',
      render: (name, record) => (
        <Space>
          <SafetyCertificateOutlined style={{ color: '#1890ff' }} />
          <span>{name as string}</span>
        </Space>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (cat) => <Tag color="blue">{getCategoryLabel(cat as string)}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'compile_status',
      key: 'compile_status',
      width: 90,
      render: (status) => (
        <Badge
          status={(status as string) === 'active' || (status as string) === 'enabled' ? 'success' : 'default'}
          text={(status as string) === 'active' || (status as string) === 'enabled' ? '启用' : '禁用'}
        />
      ),
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 80,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 170,
    },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      render: (_, record) => (
        <Space>
          <Tooltip title="编辑">
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEditOpen(record)} />
          </Tooltip>
          <Tooltip title="编译">
            <Button type="link" size="small" icon={<CodeOutlined />} onClick={() => handleCompile(record.policy_id)} />
          </Tooltip>
          <Tooltip title="热更新">
            <Button type="link" size="small" icon={<ThunderboltOutlined />} onClick={() => {
              if (record.markdown_content) {
                handleHotUpdate(record.policy_id, record.markdown_content);
              }
            }} />
          </Tooltip>
          <Tooltip title="版本历史">
            <Button type="link" size="small" icon={<HistoryOutlined />} onClick={() => handleViewVersions(record)} />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '0 0 24px 0' }}>
      <Card
        title={
          <Space>
            <SafetyCertificateOutlined />
            <span>策略管理</span>
          </Space>
        }
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => { loadPolicies(); }}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
              创建策略
            </Button>
          </Space>
        }
      >
        <Tabs items={[
          {
            key: 'policies',
            label: (
              <Space>
                <FileTextOutlined />
                <span>策略管理</span>
                <Badge count={policies.length} style={{ backgroundColor: '#1890ff' }} />
              </Space>
            ),
            children: (
              <AdvancedTable
                columns={policyColumns}
                dataSource={policies}
                rowKey="policy_id"
                loading={loading}
                pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条策略` }}
                locale={{ emptyText: <Empty description="暂无策略" /> }}
              />
            ),
          },
        ]} />
      </Card>

      <Modal
        title={<Space><PlusOutlined /><span>创建 Markdown 策略</span></Space>}
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onOk={() => createForm.submit()}
        okText="创建"
        cancelText="取消"
        width={700}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="策略名称" rules={[{ required: true, message: '请输入策略名称' }]}>
            <Input placeholder="例如: 分析师访问控制策略" />
          </Form.Item>
          <Form.Item name="category" label="策略分类" initialValue="access_control">
            <Select>
              {POLICY_CATEGORIES.map(cat => (
                <Select.Option key={cat} value={cat}>{getCategoryLabel(cat)}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="description" label="策略描述">
            <Input.TextArea rows={2} placeholder="简要描述策略用途" />
          </Form.Item>
          <Form.Item
            name="markdown_content"
            label={
              <Space>
                <span>策略内容 (Markdown DSL)</span>
                <Tag color="green">自动编译为 Rego</Tag>
              </Space>
            }
            rules={[{ required: true, message: '请输入策略内容' }]}
          >
            <TextArea
              rows={12}
              placeholder={`## 规则: 分析师访问控制\n当 [角色为分析师] 且 [密级<=secret] 时 [允许]\n\n## 规则: 禁止跨空间访问\n当 [工作空间为其他空间] 时 [拒绝]`}
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={<Space><EditOutlined /><span>编辑策略</span></Space>}
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        onOk={() => editForm.submit()}
        okText="热更新"
        cancelText="取消"
        width={700}
      >
        <Form form={editForm} layout="vertical" onFinish={handleEditSave}>
          <Form.Item name="name" label="策略名称">
            <Input disabled />
          </Form.Item>
          <Form.Item name="description" label="策略描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item
            name="markdown_content"
            label={
              <Space>
                <span>策略内容 (Markdown DSL)</span>
                <Tag color="orange">热更新将编译并替换当前策略</Tag>
              </Space>
            }
          >
            <TextArea rows={12} style={{ fontFamily: 'monospace' }} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={<Space><HistoryOutlined /><span>版本历史</span></Space>}
        open={versionModalOpen}
        onCancel={() => setVersionModalOpen(false)}
        footer={null}
        width={600}
      >
        <Timeline
          items={policyVersions.map((v) => ({
            color: v.status === 'active' ? 'green' : 'gray',
            children: (
              <div>
                <div style={{ fontWeight: 600 }}>版本 {v.version} <Tag color={v.status === 'active' ? 'green' : 'default'}>{v.status}</Tag></div>
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>{v.created_at}</div>
              </div>
            ),
          }))}
        />
        {policyVersions.length === 0 && <Empty description="暂无版本历史" />}
      </Modal>
    </div>
  );
};

export default PolicyPage;
