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
import { useI18n } from '@/modules/shared/hooks/useI18n';

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

const PolicyPage: React.FC = () => {
  const { t } = useI18n();
  const {
    policies,
    policyVersions,
    loading,
    loadPolicies,
    loadPolicyVersions,
    savePolicy,
    compilePolicy,
    hotUpdate,
  } = useAuditStore();

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [versionModalOpen, setVersionModalOpen] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);

  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const getCategoryLabel = (cat: string) => {
    const labels: Record<string, string> = {
      access_control: t('访问控制'),
      data_privacy: t('数据隐私'),
      compliance: t('合规审计'),
      security: t('安全策略'),
      workflow: t('工作流控制'),
      custom: t('自定义'),
    };
    return labels[cat] || cat;
  };

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
      message.success(t('策略创建成功'));
      setCreateModalOpen(false);
      createForm.resetFields();
    }
  };

  const handleCompile = async (policyId: string) => {
    await compilePolicy(policyId);
    const status = useAuditStore.getState().compileStatus[policyId];
    if (status?.status === 'success') {
      message.success(t('编译成功'));
    } else {
      message.error(t('编译失败: {{error}}', { error: status?.errors?.join(', ') || t('未知错误') }));
    }
  };

  const handleHotUpdate = async (policyId: string, markdownContent: string) => {
    try {
      await hotUpdate(policyId, markdownContent);
      message.success(t('热更新完成'));
    } catch (error) {
      message.error(t('热更新失败: {{error}}', { error: String(error) }));
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
      title: t('策略名称'),
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
      title: t('分类'),
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (cat) => <Tag color="blue">{getCategoryLabel(cat as string)}</Tag>,
    },
    {
      title: t('状态'),
      dataIndex: 'compile_status',
      key: 'compile_status',
      width: 90,
      render: (status) => (
        <Badge
          status={(status as string) === 'active' || (status as string) === 'enabled' ? 'success' : 'default'}
          text={(status as string) === 'active' || (status as string) === 'enabled' ? t('启用') : t('禁用')}
        />
      ),
    },
    {
      title: t('版本'),
      dataIndex: 'version',
      key: 'version',
      width: 80,
    },
    {
      title: t('更新时间'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 170,
    },
    {
      title: t('操作'),
      key: 'actions',
      width: 220,
      render: (_, record) => (
        <Space>
          <Tooltip title={t('编辑')}>
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEditOpen(record)} />
          </Tooltip>
          <Tooltip title={t('编译')}>
            <Button type="link" size="small" icon={<CodeOutlined />} onClick={() => handleCompile(record.policy_id)} />
          </Tooltip>
          <Tooltip title={t('热更新')}>
            <Button type="link" size="small" icon={<ThunderboltOutlined />} onClick={() => {
              if (record.markdown_content) {
                handleHotUpdate(record.policy_id, record.markdown_content);
              }
            }} />
          </Tooltip>
          <Tooltip title={t('版本历史')}>
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
            <span>{t('策略管理')}</span>
          </Space>
        }
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => { loadPolicies(); }}>
              {t('刷新')}
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
              {t('创建策略')}
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
                <span>{t('策略管理')}</span>
                <Badge count={policies.length} style={{ backgroundColor: '#1890ff' }} />
              </Space>
            ),
            children: (
              <AdvancedTable
                columns={policyColumns}
                dataSource={policies}
                rowKey="policy_id"
                loading={loading}
                pagination={{ pageSize: 10, showTotal: (total) => t('共 {{count}} 条策略', { count: total }) }}
                locale={{ emptyText: <Empty description={t('暂无策略')} /> }}
              />
            ),
          },
        ]} />
      </Card>

      <Modal
        title={<Space><PlusOutlined /><span>{t('创建 Markdown 策略')}</span></Space>}
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onOk={() => createForm.submit()}
        okText={t('创建')}
        cancelText={t('取消')}
        width={700}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label={t('策略名称')} rules={[{ required: true, message: t('请输入策略名称') }]}>
            <Input placeholder={t('例如: 分析师访问控制策略')} />
          </Form.Item>
          <Form.Item name="category" label={t('策略分类')} initialValue="access_control">
            <Select>
              {POLICY_CATEGORIES.map(cat => (
                <Select.Option key={cat} value={cat}>{getCategoryLabel(cat)}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="description" label={t('策略描述')}>
            <Input.TextArea rows={2} placeholder={t('简要描述策略用途')} />
          </Form.Item>
          <Form.Item
            name="markdown_content"
            label={
              <Space>
                <span>{t('策略内容 (Markdown DSL)')}</span>
                <Tag color="green">{t('自动编译为 Rego')}</Tag>
              </Space>
            }
            rules={[{ required: true, message: t('请输入策略内容') }]}
          >
            <TextArea
              rows={12}
              placeholder={t('## 规则: 分析师访问控制\n当 [角色为分析师] 且 [密级<=secret] 时 [允许]\n\n## 规则: 禁止跨空间访问\n当 [工作空间为其他空间] 时 [拒绝]')}
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={<Space><EditOutlined /><span>{t('编辑策略')}</span></Space>}
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        onOk={() => editForm.submit()}
        okText={t('热更新')}
        cancelText={t('取消')}
        width={700}
      >
        <Form form={editForm} layout="vertical" onFinish={handleEditSave}>
          <Form.Item name="name" label={t('策略名称')}>
            <Input disabled />
          </Form.Item>
          <Form.Item name="description" label={t('策略描述')}>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item
            name="markdown_content"
            label={
              <Space>
                <span>{t('策略内容 (Markdown DSL)')}</span>
                <Tag color="orange">{t('热更新将编译并替换当前策略')}</Tag>
              </Space>
            }
          >
            <TextArea rows={12} style={{ fontFamily: 'monospace' }} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={<Space><HistoryOutlined /><span>{t('版本历史')}</span></Space>}
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
                <div style={{ fontWeight: 600 }}>{t('版本 {{count}}', { count: v.version })} <Tag color={v.status === 'active' ? 'green' : 'default'}>{v.status}</Tag></div>
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>{v.created_at}</div>
              </div>
            ),
          }))}
        />
        {policyVersions.length === 0 && <Empty description={t('暂无版本历史')} />}
      </Modal>
    </div>
  );
};

export default PolicyPage;
