import { useState } from 'react';
import { Card, Tabs, Table, Button, Tag, Space, Form, Input, Select, Row, Col, Statistic } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';

interface OPACluster {
  id: string;
  name: string;
  url: string;
  status: 'active' | 'inactive';
  version: string;
  lastSync: string;
}

interface Role {
  id: string;
  name: string;
  description: string;
  permissions: string[];
  userCount: number;
  createdAt: string;
}

interface OPAPolicy {
  id: string;
  name: string;
  module: string;
  path: string;
  rules: number;
  status: 'active' | 'inactive';
  lastModified: string;
}

export function ConfigCenter() {
  const [opaPolicies] = useState<OPAPolicy[]>([
    {
      id: 'policy-001',
      name: '工作空间访问策略',
      module: 'workspace.auth',
      path: '/policies/workspace/auth.rego',
      rules: 15,
      status: 'active',
      lastModified: '2026-04-19 10:30:00',
    },
    {
      id: 'policy-002',
      name: '数据访问策略',
      module: 'data.access',
      path: '/policies/data/access.rego',
      rules: 22,
      status: 'active',
      lastModified: '2026-04-18 15:20:00',
    },
    {
      id: 'policy-003',
      name: '资源配额策略',
      module: 'resource.quota',
      path: '/policies/resource/quota.rego',
      rules: 8,
      status: 'inactive',
      lastModified: '2026-04-15 09:00:00',
    },
  ]);

  const [roles] = useState<Role[]>([
    {
      id: 'role-001',
      name: '系统管理员',
      description: '拥有系统所有权限',
      permissions: ['*'],
      userCount: 2,
      createdAt: '2026-01-01 00:00:00',
    },
    {
      id: 'role-002',
      name: '工作空间管理员',
      description: '管理工作空间内的资源',
      permissions: ['workspace:*', 'scenario:*', 'ingest:*'],
      userCount: 5,
      createdAt: '2026-01-15 00:00:00',
    },
    {
      id: 'role-003',
      name: '普通用户',
      description: '查看和管理自己的资源',
      permissions: ['scenario:read', 'scenario:write', 'ingest:read'],
      userCount: 20,
      createdAt: '2026-02-01 00:00:00',
    },
  ]);

  const [clusters] = useState<OPACluster[]>([
    {
      id: 'cluster-001',
      name: '主 OPA 集群',
      url: 'http://localhost:8181',
      status: 'active',
      version: '0.58.0',
      lastSync: '2026-04-19 14:00:00',
    },
  ]);

  const policyColumns = [
    {
      title: '策略名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: OPAPolicy) => (
        <Space>
          <span style={{ fontWeight: 500 }}>{name}</span>
          <Tag color={record.status === 'active' ? 'green' : 'red'}>
            {record.status === 'active' ? '启用' : '停用'}
          </Tag>
        </Space>
      ),
    },
    {
      title: '模块',
      dataIndex: 'module',
      key: 'module',
    },
    {
      title: '路径',
      dataIndex: 'path',
      key: 'path',
      ellipsis: true,
    },
    {
      title: '规则数',
      dataIndex: 'rules',
      key: 'rules',
    },
    {
      title: '最后修改',
      dataIndex: 'lastModified',
      key: 'lastModified',
    },
    {
      title: '操作',
      key: 'action',
      render: () => (
        <Space>
          <Button type="link" icon={<EditOutlined />}>编辑</Button>
          <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
        </Space>
      ),
    },
  ];

  const roleColumns = [
    {
      title: '角色名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => <span style={{ fontWeight: 500 }}>{name}</span>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '权限',
      dataIndex: 'permissions',
      key: 'permissions',
      render: (permissions: string[]) => (
        <Space wrap>
          {permissions.slice(0, 3).map((perm) => (
            <Tag key={perm} color="blue">{perm}</Tag>
          ))}
          {permissions.length > 3 && <Tag>+{permissions.length - 3}</Tag>}
        </Space>
      ),
    },
    {
      title: '用户数',
      dataIndex: 'userCount',
      key: 'userCount',
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
    },
    {
      title: '操作',
      key: 'action',
      render: () => (
        <Space>
          <Button type="link" icon={<EditOutlined />}>编辑</Button>
          <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
        </Space>
      ),
    },
  ];

  const clusterColumns = [
    {
      title: '集群名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: OPACluster) => (
        <Space>
          <span style={{ fontWeight: 500 }}>{name}</span>
          <Tag color={record.status === 'active' ? 'green' : 'red'}>
            {record.status === 'active' ? '在线' : '离线'}
          </Tag>
        </Space>
      ),
    },
    {
      title: 'URL',
      dataIndex: 'url',
      key: 'url',
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
    },
    {
      title: '最后同步',
      dataIndex: 'lastSync',
      key: 'lastSync',
    },
    {
      title: '操作',
      key: 'action',
      render: () => (
        <Space>
          <Button type="link" icon={<ReloadOutlined />}>同步</Button>
          <Button type="link" danger>删除</Button>
        </Space>
      ),
    },
  ];

  const items = [
    {
      key: 'policies',
      label: 'OPA 策略',
      children: (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Button type="primary" icon={<PlusOutlined />}>创建策略</Button>
            <Button icon={<ReloadOutlined />}>刷新</Button>
          </Space>
          <Table
            columns={policyColumns}
            dataSource={opaPolicies}
            rowKey="id"
            pagination={false}
          />
        </div>
      ),
    },
    {
      key: 'roles',
      label: '角色管理',
      children: (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Button type="primary" icon={<PlusOutlined />}>创建角色</Button>
            <Button icon={<ReloadOutlined />}>刷新</Button>
          </Space>
          <Table
            columns={roleColumns}
            dataSource={roles}
            rowKey="id"
            pagination={false}
          />
        </div>
      ),
    },
    {
      key: 'clusters',
      label: 'OPA 集群',
      children: (
        <div>
          <Row gutter={[16, 16]}>
            <Col span={6}>
              <Card>
                <Statistic title="总集群数" value={clusters.length} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="在线集群" value={clusters.filter(c => c.status === 'active').length} styles={{ content: { color: '#52c41a' } }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="离线集群" value={clusters.filter(c => c.status === 'inactive').length} styles={{ content: { color: '#ff4d4f' } }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="总策略数" value={opaPolicies.length} />
              </Card>
            </Col>
          </Row>
          <Space style={{ marginBottom: 16, marginTop: 16 }}>
            <Button type="primary" icon={<PlusOutlined />}>添加集群</Button>
            <Button icon={<ReloadOutlined />}>刷新</Button>
          </Space>
          <Table
            columns={clusterColumns}
            dataSource={clusters}
            rowKey="id"
            pagination={false}
          />
        </div>
      ),
    },
    {
      key: 'settings',
      label: '系统设置',
      children: (
        <Card title="系统配置">
          <Form layout="vertical">
            <Form.Item label="系统名称">
              <Input placeholder="请输入系统名称" defaultValue="Graphiti 知识图谱管理系统" />
            </Form.Item>
            <Form.Item label="系统描述">
              <Input.TextArea rows={3} placeholder="请输入系统描述" defaultValue="用于管理和可视化知识图谱的系统" />
            </Form.Item>
            <Form.Item label="数据保留天数">
              <Select
                defaultValue="30"
                options={[
                  { value: '7', label: '7 天' },
                  { value: '30', label: '30 天' },
                  { value: '90', label: '90 天' },
                  { value: '365', label: '1 年' },
                ]}
              />
            </Form.Item>
            <Form.Item>
              <Button type="primary">保存配置</Button>
            </Form.Item>
          </Form>
        </Card>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card title="配置中心">
        <Tabs items={items} />
      </Card>
    </div>
  );
}