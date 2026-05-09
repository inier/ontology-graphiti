import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Button,
  Space,
  Tag,
  Table,
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

const PolicyManagement: React.FC = () => {
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
      message.success('策略创建成功');
      setCreateModalOpen(false);
      createForm.resetFields();
      fetchPolicies();
    } catch (error) {
      message.error(`创建失败: ${error}`);
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
      message.success('策略更新成功');
      setEditModalOpen(false);
      editForm.resetFields();
      fetchPolicies();
    } catch (error) {
      message.error(`更新失败: ${error}`);
    }
  };

  const handleToggleStatus = async (policy: Policy, enabled: boolean) => {
    try {
      await apiService.togglePolicyStatus(policy.policy_id, enabled);
      message.success(`策略已${enabled ? '启用' : '禁用'}`);
      fetchPolicies();
    } catch (error) {
      message.error(`操作失败: ${error}`);
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
      message.error(`获取详情失败: ${error}`);
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
      title: '策略名称',
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
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (cat: string) => (
        <Tag color="blue">{getCategoryLabel(cat)}</Tag>
      ),
    },
    {
      title: '状态',
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
      width: 160,
      render: (_, record: Policy) => (
        <Space>
          <Tooltip title="查看详情">
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => handleViewDetail(record)}
            />
          </Tooltip>
          <Tooltip title="编辑">
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
            <span>OPA 策略管理</span>
            <Badge count={policies.length} style={{ backgroundColor: '#1890ff' }} />
          </Space>
        }
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchPolicies}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalOpen(true)}
            >
              创建策略
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={policies}
          rowKey="policy_id"
          loading={loading}
          pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条策略` }}
          locale={{ emptyText: <Empty description="暂无策略，点击创建按钮添加" /> }}
        />
      </Card>

      {/* 创建策略模态框 */}
      <Modal
        title={
          <Space>
            <PlusOutlined />
            <span>创建 OPA 策略</span>
          </Space>
        }
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onOk={() => createForm.submit()}
        okText="创建"
        cancelText="取消"
        width={700}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreate}
        >
          <Form.Item
            name="name"
            label="策略名称"
            rules={[{ required: true, message: '请输入策略名称' }]}
          >
            <Input placeholder="例如: 分析师访问控制策略" />
          </Form.Item>
          <Form.Item
            name="category"
            label="策略分类"
            rules={[{ required: true, message: '请选择分类' }]}
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
            label="策略描述"
            rules={[{ required: true, message: '请输入描述' }]}
          >
            <Input.TextArea rows={2} placeholder="简要描述策略用途" />
          </Form.Item>
          <Form.Item
            name="markdown_content"
            label={
              <Space>
                <span>策略内容 (Markdown)</span>
                <Tag color="green">将自动转换为 Rego</Tag>
              </Space>
            }
            rules={[{ required: true, message: '请输入策略内容' }]}
          >
            <TextArea
              rows={12}
              placeholder={`# 访问控制策略

## 规则
允许分析师在值班时间访问情报数据。

## 条件
- 用户角色: analyst
- 时间: 工作日 9:00-18:00
- 数据密级: <= SECRET

## 操作
- 允许读取
- 拒绝写入
`}
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
            <span>策略详情</span>
          </Space>
        }
        open={detailModalOpen}
        onCancel={() => { setDetailModalOpen(false); setDetailData(null); }}
        footer={null}
        width={800}
        loading={detailLoading}
      >
        {detailData && (
          <Descriptions bordered column={2} size="small">
            <Descriptions.Item label="策略ID">{detailData.policy_id as string}</Descriptions.Item>
            <Descriptions.Item label="策略名称">{detailData.name as string}</Descriptions.Item>
            <Descriptions.Item label="分类">
              <Tag color="blue">{getCategoryLabel(detailData.category as string)}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Badge
                status={(detailData.status as string) === 'active' ? 'success' : 'default'}
                text={detailData.status as string}
              />
            </Descriptions.Item>
            <Descriptions.Item label="版本">{detailData.version as string}</Descriptions.Item>
            <Descriptions.Item label="创建时间">{detailData.created_at as string}</Descriptions.Item>
            <Descriptions.Item label="更新时间" span={2}>{detailData.updated_at as string}</Descriptions.Item>
            <Descriptions.Item label="描述" span={2}>{detailData.description as string}</Descriptions.Item>
          </Descriptions>
        )}
        {detailData?.markdown_content && (
          <>
            <Divider orientation="left">Markdown 策略内容</Divider>
            <Card size="small" style={{ maxHeight: 300, overflow: 'auto' }}>
              <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 13 }}>
                {detailData.markdown_content as string}
              </pre>
            </Card>
          </>
        )}
        {detailData?.rego_content && (
          <>
            <Divider orientation="left">
              <Space>
                <CodeOutlined />
                <span>生成的 Rego 代码</span>
              </Space>
            </Divider>
            <Card size="small" style={{ maxHeight: 300, overflow: 'auto', background: '#f6f8fa' }}>
              <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 12 }}>
                {detailData.rego_content as string}
              </pre>
            </Card>
          </>
        )}
        {!detailData?.markdown_content && !detailData?.rego_content && !detailLoading && (
          <Empty description="暂无更多详情" />
        )}
      </Modal>

      {/* 编辑策略模态框 */}
      <Modal
        title={
          <Space>
            <EditOutlined />
            <span>编辑策略</span>
          </Space>
        }
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        onOk={() => editForm.submit()}
        okText="保存"
        cancelText="取消"
        width={700}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleUpdate}
        >
          <Form.Item
            name="name"
            label="策略名称"
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="description"
            label="策略描述"
          >
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item
            name="markdown_content"
            label="策略内容 (Markdown)"
          >
            <TextArea rows={12} style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select>
              <Select.Option value="active">启用</Select.Option>
              <Select.Option value="inactive">禁用</Select.Option>
              <Select.Option value="draft">草稿</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default PolicyManagement;