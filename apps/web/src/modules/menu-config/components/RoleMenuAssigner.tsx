/**
 * RoleMenuAssigner — 可复用的角色菜单权限分配组件。
 *
 * 使用场景：
 * - MenuConfigPage 的「角色权限分配」Tab
 * - RoleManager 的角色编辑 Modal
 * - 任何需要为角色勾选菜单树的场景
 *
 * Props 说明：
 * - roles: 角色列表（id/name/description）
 * - selectedRoleId: 当前选中角色
 * - onSelectRole: 切换角色回调
 * - menuTreeItems: 菜单扁平列表（用于 titleRender 查找）
 * - menuTreeNode: 菜单树节点（Ant Design Tree treeData）
 * - checkedMenuIds: 已勾选的菜单ID集合
 * - onCheck: 勾选变化回调 (checkedKeys: string[]) => void
 * - onSave: 保存回调 () => Promise<void>
 * - roleLoading: 加载角色菜单中
 * - roleSaving: 保存中
 * - extraRoleActions: 角色列表中额外的操作按钮
 */
import React from 'react';
import {
  Card, Tree, Button, Space, Tag, Typography, Avatar, List, Empty, Spin,
} from 'antd';
import { ReloadOutlined, SaveOutlined } from '@ant-design/icons';
import type { TreeDataNode } from 'antd';
import type { MenuItem } from '../services/menuConfigApi';
import { resolveIcon } from '../utils/iconResolver';

const { Text } = Typography;

export interface RoleSummary {
  id: string;
  name: string;
  description?: string;
  color?: string;
}

const MENU_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  directory: { label: '目录', color: 'blue' },
  menu: { label: '菜单', color: 'green' },
  action: { label: '操作', color: 'orange' },
};

function getItemIcon(item: MenuItem): React.ReactNode {
  switch (item.menu_type) {
    case 'directory': return resolveIcon(item.icon || 'FolderOutlined');
    case 'action': return resolveIcon(item.icon || 'ThunderboltOutlined');
    default: return resolveIcon(item.icon || 'FileOutlined');
  }
}

const ROLE_AVATAR_COLORS = [
  '#f5222d', '#fa8c16', '#1890ff', '#52c41a', '#8c8c8c',
  '#722ed1', '#13c2c2', '#eb2f96', '#2f54eb', '#595959',
];

function getRoleColor(index: number): string {
  return ROLE_AVATAR_COLORS[index % ROLE_AVATAR_COLORS.length];
}

export interface RoleMenuAssignerProps {
  roles: RoleSummary[];
  selectedRoleId: string;
  onSelectRole: (roleId: string) => void;
  menuTreeItems: MenuItem[];
  menuTreeNode: TreeDataNode[];
  checkedMenuIds: string[];
  onCheck: (checkedKeys: string[]) => void;
  onSave: () => Promise<void>;
  roleLoading: boolean;
  roleSaving?: boolean;
  onReset?: () => void;
}

export function RoleMenuAssigner({
  roles,
  selectedRoleId,
  onSelectRole,
  menuTreeItems,
  menuTreeNode,
  checkedMenuIds,
  onCheck,
  onSave,
  roleLoading,
  roleSaving = false,
  onReset,
}: RoleMenuAssignerProps) {
  const selectedRole = roles.find((r) => r.id === selectedRoleId) || roles[0];

  const handleTreeCheck = (
    checked: React.Key[] | { checked: React.Key[]; halfChecked: React.Key[] },
  ) => {
    const keys = Array.isArray(checked) ? checked : checked.checked;
    onCheck(keys as string[]);
  };

  return (
    <div style={{ flex: 1, display: 'flex', gap: 16, minHeight: 0 }}>
      {/* 左侧：角色列表 */}
      <Card
        title="角色列表"
        size="small"
        style={{
          width: 320,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
        }}
        styles={{ body: { padding: 0, overflow: 'auto', flex: 1 }}}
      >
        {roles.length > 0 ? (
          <List
            dataSource={roles}
            renderItem={(role, index) => (
              <List.Item
                onClick={() => onSelectRole(role.id)}
                style={{
                  cursor: 'pointer',
                  backgroundColor:
                    selectedRoleId === role.id ? '#e6f7ff' : 'transparent',
                  borderLeft: `3px solid ${
                    selectedRoleId === role.id
                      ? getRoleColor(index)
                      : 'transparent'
                  }`,
                  padding: '12px 16px',
                  transition: 'background-color 0.2s',
                }}
              >
                <List.Item.Meta
                  avatar={
                    <Avatar
                      style={{ backgroundColor: getRoleColor(index) }}
                    >
                      {role.name.charAt(0).toUpperCase()}
                    </Avatar>
                  }
                  title={
                    <Text strong={selectedRoleId === role.id}>
                      {role.name}
                    </Text>
                  }
                  description={
                    <Text
                      type="secondary"
                      style={{ fontSize: 12 }}
                      ellipsis
                    >
                      {role.description || '暂无描述'}
                    </Text>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty
            description="暂无角色数据"
            style={{ padding: 24 }}
          />
        )}
      </Card>

      {/* 右侧：权限树 */}
      <Card
        title={
          selectedRole
            ? `权限范围 — ${selectedRole.name}`
            : '权限范围'
        }
        size="small"
        extra={
          <Space>
            {onReset && (
              <Button
                onClick={onReset}
                loading={roleLoading}
                icon={<ReloadOutlined />}
              >
                重置
              </Button>
            )}
            <Button
              type="primary"
              onClick={onSave}
              loading={roleSaving}
              icon={<SaveOutlined />}
            >
              保存权限
            </Button>
          </Space>
        }
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
        }}
        styles={{ body: { overflow: 'auto', flex: 1, padding: 12 }}}
      >
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          勾选角色可访问的菜单与操作节点，保存后即时生效。
        </Text>

        {roleLoading ? (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin />
            <Text type="secondary" style={{ display: 'block', marginTop: 12 }}>
              加载菜单权限…
            </Text>
          </div>
        ) : menuTreeNode.length > 0 ? (
          <Tree
            treeData={menuTreeNode}
            checkable
            checkedKeys={checkedMenuIds}
            onCheck={handleTreeCheck}
            titleRender={(node) => {
              const item = menuTreeItems.find((i) => i.id === node.key);
              if (!item) return node.title as React.ReactNode;
              return (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  {getItemIcon(item)}
                  <span>{item.name}</span>
                  <Tag
                    style={{ fontSize: 11, flexShrink: 0 }}
                    color={
                      MENU_TYPE_LABELS[item.menu_type]?.color || 'default'
                    }
                  >
                    {MENU_TYPE_LABELS[item.menu_type]?.label || item.menu_type}
                  </Tag>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {item.code}
                  </Text>
                </span>
              );
            }}
            style={{ minWidth: 420 }}
          />
        ) : (
          <Empty description="暂无菜单项，请先创建菜单" />
        )}
      </Card>
    </div>
  );
}
