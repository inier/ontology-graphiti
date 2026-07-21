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
  Descriptions,
  Badge,
  Tooltip,
  Empty,
  Divider,
  Switch,
  Typography,
  Row,
  Col,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SafetyCertificateOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import { apiService } from '@/modules/shared/services/api';
import type { ColumnsType } from 'antd/es/table';
import { AdvancedTable } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { TextArea } = Input;
const { Paragraph, Text } = Typography;

interface Policy {
  policy_id: string;
  name: string;
  description: string;
  category: string;
  status: string;
  version: string;
  updated_at: string;
}

const POLICY_CATEGORIES = [
  'access_control',
  'data_privacy',
  'compliance',
  'security',
  'workflow',
  'custom',
];

const PolicyManagement: React.FC = () => {
  const { t } = useI18n();

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
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);
  const [detailData, setDetailData] = useState<Record<string, unknown> | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const fetchPolicies = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiService.listPolicies({ limit: 100 });
      setPolicies(response.policies);
    } catch (error) {
      console.error('获取策略列表失败', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  const handleCreate = async (values: Record<string, unknown>) => {
    try {
      await apiService.createPolicy({
        name: values.name as string,
        description: values.description as string,
        markdown_content: values.markdown_content as string,
        category: values.category as string,
      });
      message.success(t('策略创建成功'));
      setCreateModalOpen(false);
      createForm.resetFields();
      fetchPolicies();
    } catch (error) {
      message.error(t('创建失败') + `: ${error}`);
    }
  };

  const handleUpdate = async (values: Record<string, unknown>) => {
    if (!selectedPolicy) return;
    try {
      await apiService.updatePolicy(selectedPolicy.policy_id, {
        name: values.name as string | undefined,
        description: values.description as string | undefined,
        markdown_content: values.markdown_content as string | undefined,
        status: values.status as string | undefined,
      });
      message.success(t('策略更新成功'));
      setEditModalOpen(false);
      editForm.resetFields();
      fetchPolicies();
    } catch (error) {
      message.error(t('更新失败') + `: ${error}`);
    }
  };

  const handleToggleStatus = async (policy: Policy, enabled: boolean) => {
    try {
      await apiService.togglePolicyStatus(policy.policy_id, enabled);
      message.success(enabled ? t('策略已启用') : t('策略已禁用'));
      fetchPolicies();
    } catch (error) {
      message.error(t('操作失败') + `: ${error}`);
    }
  };

  const handleViewDetail = async (policy: Policy) => {
    setSelectedPolicy(policy);
    setDetailModalOpen(true);
    setDetailLoading(true);
    try {
      const detail = await apiService.getPolicy(policy.policy_id);
      setDetailData(detail as unknown as Record<string, unknown>);
    } catch (error) {
      message.error(t('获取详情失败') + `: ${error}`);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleEditOpen = (policy: Policy) => {
    setSelectedPolicy(policy);
    editForm.setFieldsValue({
      name: policy.name,
      description: policy.description,
      status: policy.status,
    });
    setEditModalOpen(true);
  };

  const columns: ColumnsType<Policy> = [
    {
      title: t('策略名称'),
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: Policy) => (
        <Space>
          <SafetyCertificateOutlined style={{ color: '#1890ff' }} />
          <a onClick={() => handleViewDetail(record)}>{name}</a>
        </Space>
      ),
    },
    {
      title: t('分类'),
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (cat: string) => (
        <Tag color="blue">{getCategoryLabel(cat)}</Tag>
      ),
    },
    {
      title: t('状态'),
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string, record: Policy) => (
        <Switch
          checked={status === 'active' || status === 'enabled'}
          onChange={(checked) => handleToggleStatus(record, checked)}
          checkedChildren={<CheckCircleOutlined />}
          unCheckedChildren={<CloseCircleOutlined />}
          size="small"
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
      width: 160,
      render: (_, record: Policy) => (
        <Space>
          <Tooltip title={t('查看详情')}>
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => handleViewDetail(record)}
            />
          </Tooltip>
          <Tooltip title={t('编辑')}>
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEditOpen(record)}
            />
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
            <span>{t('OPA 策略管理')}</span>
            <Badge count={policies.length} style={{ backgroundColor: '#1890ff' }} />
          </Space>
        }
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchPolicies}>
              {t('刷新')}
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
          pagination={{ pageSize: 10, showTotal: (total) => t('共 {{n}} 条策略', { n: total }) }}
          locale={{ emptyText: <Empty description={t('暂无策略，点击创建按钮添加')} /> }}
        />
      </Card>

      {/* 创建策略模态框 */}
      <Modal
        title={
          <Space>
            <PlusOutlined />
            <span>{t('创建 OPA 策略')}</span>
          </Space>
        }
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onOk={() => createForm.submit()}
        okText={t('创建')}
        cancelText={t('取消')}
        width={700}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreate}
        >
          <Form.Item
            name="name"
            label={t('策略名称')}
            rules={[{ required: true, message: t('请输入策略名称') }]}
          >
            <Input placeholder={t('例如: 分析师访问控制策略')} />
          </Form.Item>
          <Form.Item
            name="category"
            label={t('策略分类')}
            rules={[{ required: true, message: t('请选择分类') }]}
            initialValue="access_control"
          >
            <Select>
              {POLICY_CATEGORIES.map(cat => (
                <Select.Option key={cat} value={cat}>{getCategoryLabel(cat)}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="description"
            label={t('策略描述')}
            rules={[{ required: true, message: t('请输入描述') }]}
          >
            <Input.TextArea rows={2} placeholder={t('简要描述策略用途')} />
          </Form.Item>
          <Form.Item
            name="markdown_content"
            label={
              <Space>
                <span>{t('策略内容 (Markdown)')}</span>
                <Tag color="green">{t('将自动转换为 Rego')}</Tag>
              </Space>
            }
            rules={[{ required: true, message: t('请输入策略内容') }]}
          >
            <TextArea
              rows={12}
              placeholder={t(`# 访问控制策略

## 规则
允许分析师在值班时间访问情报数据。

## 条件
- 用户角色: analyst
- 时间: 工作日 9:00-18:00
- 数据密级: <= SECRET

## 操作
- 允许读取
- 拒绝写入
`)}
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 策略详情模态框 */}
      <Modal
        title={
          <Space>
            <EyeOutlined />
            <span>{t('策略详情')}</span>
          </Space>
        }
        open={detailModalOpen}
        onCancel={() => { setDetailModalOpen(false); setDetailData(null); }}
        footer={null}
        width={800}
        loading={detailLoading}
      >
        {detailData && (
          <Descriptions column={2}>
            <Descriptions.Item label={t('策略ID')}>{detailData.policy_id as string}</Descriptions.Item>
            <Descriptions.Item label={t('策略名称')}>{detailData.name as string}</Descriptions.Item>
            <Descriptions.Item label={t('分类')}>
              <Tag color="blue">{getCategoryLabel(detailData.category as string)}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('状态')}>
              <Badge
                status={(detailData.status as string) === 'active' ? 'success' : 'default'}
                text={detailData.status as string}
              />
            </Descriptions.Item>
            <Descriptions.Item label={t('版本')}>{detailData.version as string}</Descriptions.Item>
            <Descriptions.Item label={t('创建时间')}>{detailData.created_at as string}</Descriptions.Item>
            <Descriptions.Item label={t('更新时间')} span={2}>{detailData.updated_at as string}</Descriptions.Item>
            <Descriptions.Item label={t('描述')} span={2}>{detailData.description as string}</Descriptions.Item>
          </Descriptions>
        )}
        {Boolean(detailData?.markdown_content) && (
          <>
            <Divider titlePlacement="left">{t('Markdown 策略内容')}</Divider>
            <Card size="small" style={{ maxHeight: 300, overflow: 'auto' }}>
              <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 13 }}>
                {String(detailData?.markdown_content)}
              </pre>
            </Card>
          </>
        )}
        {Boolean(detailData?.rego_content) && (
          <>
            <Divider titlePlacement="left">
              <Space>
                <CodeOutlined />
                <span>{t('生成的 Rego 代码')}</span>
              </Space>
            </Divider>
            <Card size="small" style={{ maxHeight: 300, overflow: 'auto', background: '#f6f8fa' }}>
              <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 12 }}>
                {String(detailData?.rego_content)}
              </pre>
            </Card>
          </>
        )}
        {!detailData?.markdown_content && !detailData?.rego_content && !detailLoading && (
          <Empty description={t('暂无更多详情')} />
        )}
      </Modal>

      {/* 编辑策略模态框 */}
      <Modal
        title={
          <Space>
            <EditOutlined />
            <span>{t('编辑策略')}</span>
          </Space>
        }
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        onOk={() => editForm.submit()}
        okText={t('保存')}
        cancelText={t('取消')}
        width={700}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleUpdate}
        >
          <Form.Item
            name="name"
            label={t('策略名称')}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="description"
            label={t('策略描述')}
          >
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item
            name="markdown_content"
            label={t('策略内容 (Markdown)')}
          >
            <TextArea rows={12} style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="status" label={t('状态')}>
            <Select>
              <Select.Option value="active">{t('启用')}</Select.Option>
              <Select.Option value="inactive">{t('禁用')}</Select.Option>
              <Select.Option value="draft">{t('草稿')}</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default PolicyManagement;