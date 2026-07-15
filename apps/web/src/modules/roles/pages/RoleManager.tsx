import { useState, useEffect, useCallback } from 'react';
import {
  Card, Button, Modal, Form, Input, Select, Space, Tag, Popconfirm, message, Row, Col,
  Statistic, Checkbox, Tabs,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import {
  listRoles, getRole, createRole, updateRole, deleteRole, listPermissions,
} from '../services/rolesApi';
import type { Role, RoleCreate, RoleUpdate, Permission } from '../types';
import { menuConfigApi } from '@/modules/menu-config/services/menuConfigApi';
import type { MenuItem as MenuConfigItem } from '@/modules/menu-config/services/menuConfigApi';
import { RoleMenuAssigner, type RoleSummary } from '@/modules/menu-config';
import { AdvancedTable } from '@/modules/shared';

const { Option } = Select;
const { TextArea } = Input;

function flattenMenuTree(items: MenuConfigItem[]): MenuConfigItem[] {
  const result: MenuConfigItem[] = [];
  const walk = (nodes: MenuConfigItem[]) => {
    nodes.forEach((n) => {
      result.push(n);
      if (n.children?.length) walk(n.children);
    });
  };
  walk(items);
  return result;
}

function toTreeData(items: MenuConfigItem[]): any[] {
  return items.map((item) => ({
    key: item.id,
    title: item.name,
    children: item.children ? toTreeData(item.children) : [],
  }));
}

export function RoleManager() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [form] = Form.useForm();
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);

  /* ── 菜单权限状态 ── */
  const [menuModalVisible, setMenuModalVisible] = useState(false);
  const [menuPermissionRole, setMenuPermissionRole] = useState<Role | null>(null);
  const [menuTree, setMenuTree] = useState<MenuConfigItem[]>([]);
  const [menuFlatItems, setMenuFlatItems] = useState<MenuConfigItem[]>([]);
  const [menuRoleIds, setMenuRoleIds] = useState<string[]>([]);
  const [menuRoleLoading, setMenuRoleLoading] = useState(false);
  const [menuRoleSaving, setMenuRoleSaving] = useState(false);

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [rolesData, permissionsData] = await Promise.all([
        listRoles(), listPermissions(),
      ]);
      setRoles(rolesData);
      setPermissions(permissionsData);
    } catch (error) {
      console.error('加载数据失败', error);
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadMenuTree = useCallback(async () => {
    try {
      const data = await menuConfigApi.getFullTree();
      setMenuTree(data.tree || []);
      setMenuFlatItems(flattenMenuTree(data.tree || []));
    } catch (e: any) {
      message.error('加载菜单树失败: ' + (e.message || e));
    }
  }, []);

  const loadMenuRolePermissions = useCallback(async (roleId: string) => {
    setMenuRoleLoading(true);
    try {
      const data = await menuConfigApi.getRoleMenus(roleId);
      setMenuRoleIds(data.menu_ids || []);
    } catch (e: any) {
      message.error('加载菜单权限失败: ' + (e.message || e));
      setMenuRoleIds([]);
    } finally {
      setMenuRoleLoading(false);
    }
  }, []);

  const openMenuPermission = async (role: Role) => {
    setMenuPermissionRole(role);
    setMenuModalVisible(true);
    if (menuTree.length === 0) await loadMenuTree();
    loadMenuRolePermissions(role.id);
  };

  const saveMenuPermission = async () => {
    if (!menuPermissionRole) return;
    setMenuRoleSaving(true);
    try {
      await menuConfigApi.setRoleMenus(menuPermissionRole.id, menuRoleIds);
      message.success('菜单权限已保存');
    } catch (e: any) {
      message.error('保存失败: ' + (e.message || e));
    } finally {
      setMenuRoleSaving(false);
    }
  };

  const handleCreate = () => {
    setEditingRole(null);
    setSelectedPermissions([]);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (role: Role) => {
    setEditingRole(role);
    setSelectedPermissions(role.permissions.map((p) => p.id));
    form.setFieldsValue({
      name: role.name,
      description: role.description,
      role_type: role.role_type,
    });
    setModalVisible(true);
  };

  const handleDelete = async (roleId: string) => {
    try {
      await deleteRole(roleId);
      message.success('删除成功');
      loadData();
    } catch {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const roleData: RoleCreate | RoleUpdate = {
        ...values,
        permissions: selectedPermissions,
      };
      if (editingRole) {
        await updateRole(editingRole.id, roleData as RoleUpdate);
        message.success('更新成功');
      } else {
        await createRole(roleData as RoleCreate);
        message.success('创建成功');
      }
      setModalVisible(false);
      loadData();
    } catch {
      message.error('操作失败');
    }
  };

  const getRoleTypeColor = (roleType: string) => {
    const colors: Record<string, string> = {
      system_admin: 'red', project_owner: 'orange', team_leader: 'blue',
      member: 'green', guest: 'gray', director: 'purple', intelligence: 'cyan',
      operator: 'geekblue', analyst: 'magenta', schema_auditor: 'volcano',
    };
    return colors[roleType] || 'default';
  };

  const getRoleTypeLabel = (roleType: string) => {
    const labels: Record<string, string> = {
      system_admin: '系统管理员', project_owner: '项目所有者', team_leader: '团队领导',
      member: '成员', guest: '访客', director: '负责人', intelligence: '情报员',
      operator: '操作员', analyst: '分析员', schema_auditor: 'Schema 审计员',
    };
    return labels[roleType] || roleType;
  };

  const getPermissionScopeLabel = (scope: string) => {
    const labels: Record<string, string> = { system: '系统', project: '项目', resource: '资源', data: '数据' };
    return labels[scope] || scope;
  };

  const columns = [
    { title: '角色名称', dataIndex: 'name', key: 'name', width: 150 },
    {
      title: '角色类型', dataIndex: 'role_type', key: 'role_type', width: 120,
      render: (type: string) => <Tag color={getRoleTypeColor(type)}>{getRoleTypeLabel(type)}</Tag>,
    },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '权限数', dataIndex: 'permissions', key: 'permissions', width: 80,
      render: (p: Permission[]) => p.length,
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180,
      render: (d: string) => new Date(d).toLocaleString(),
    },
    {
      title: '操作', key: 'action', width: 260,
      render: (_: any, record: Role) => (
        <Space size="small">
          <Button type="primary" icon={<EditOutlined />} size="small" onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Button size="small" onClick={() => openMenuPermission(record)}>
            菜单权限
          </Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
            <Button danger icon={<DeleteOutlined />} size="small">删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="角色管理"
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新增角色</Button>}
      >
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Card><Statistic title="角色总数" value={roles.length} /></Card>
          </Col>
          <Col span={6}>
            <Card><Statistic title="权限总数" value={permissions.length} /></Card>
          </Col>
        </Row>

        <AdvancedTable
          columns={columns}
          dataSource={roles as unknown as readonly Record<string, unknown>[]}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      {/* 角色 CRUD Modal */}
      <Modal
        title={editingRole ? '编辑角色' : '新增角色'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="角色名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="角色描述" rules={[{ required: true }]}>
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item name="role_type" label="角色类型" rules={[{ required: true }]}>
            <Select>
              <Option value="system_admin">系统管理员</Option>
              <Option value="project_owner">项目所有者</Option>
              <Option value="team_leader">团队领导</Option>
              <Option value="member">成员</Option>
              <Option value="guest">访客</Option>
              <Option value="director">负责人</Option>
              <Option value="intelligence">情报员</Option>
              <Option value="operator">操作员</Option>
              <Option value="analyst">分析员</Option>
              <Option value="schema_auditor">Schema 审计员</Option>
            </Select>
          </Form.Item>
          <Form.Item label="权限">
            <div style={{ maxHeight: 300, overflowY: 'auto', border: '1px solid #f0f0f0', padding: 16, borderRadius: 4 }}>
              <Checkbox.Group
                options={permissions.map((p) => ({
                  label: (
                    <span style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                      <span>{p.name}</span>
                      <Tag>{getPermissionScopeLabel(p.scope)}</Tag>
                    </span>
                  ),
                  value: p.id,
                }))}
                value={selectedPermissions}
                onChange={(vals) => setSelectedPermissions(vals as string[])}
              />
            </div>
          </Form.Item>
        </Form>
      </Modal>

      {/* 菜单权限 Modal — 复用 RoleMenuAssigner */}
      <Modal
        title={menuPermissionRole ? `${menuPermissionRole.name} — 菜单权限` : '菜单权限'}
        open={menuModalVisible}
        onCancel={() => setMenuModalVisible(false)}
        footer={null}
        width={900}
        destroyOnClose
        style={{ top: 24 }}
      >
        <div style={{ height: '65vh', display: 'flex' }}>
          <RoleMenuAssigner
            roles={[{
              id: menuPermissionRole?.id || '',
              name: menuPermissionRole?.name || '',
              description: menuPermissionRole?.description || '',
            }]}
            selectedRoleId={menuPermissionRole?.id || ''}
            onSelectRole={() => {}}
            menuTreeItems={menuFlatItems}
            menuTreeNode={toTreeData(menuTree)}
            checkedMenuIds={menuRoleIds}
            onCheck={(keys) => setMenuRoleIds(keys)}
            onSave={saveMenuPermission}
            roleLoading={menuRoleLoading}
            roleSaving={menuRoleSaving}
          />
        </div>
      </Modal>
    </div>
  );
}
