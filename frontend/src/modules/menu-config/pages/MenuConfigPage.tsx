import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Card, Tree, Button, Space, Tag, Typography, Modal, Form, Input,
  Select, InputNumber, Switch, message, Popconfirm, Tooltip, Tabs,
  Empty, Badge, Descriptions, Divider,
} from 'antd';
import type { TreeDataNode } from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
  FolderOutlined, FileOutlined, ThunderboltOutlined,
  ReloadOutlined, SafetyOutlined,
} from '@ant-design/icons';
import { menuConfigApi, type MenuItem } from '../services/menuConfigApi';
import { listRoles } from '@/modules/roles/services/rolesApi';
import { RoleMenuAssigner, type RoleSummary } from '../components/RoleMenuAssigner';
import { resolveIcon, ICON_OPTIONS } from '../utils/iconResolver';
import { resolveMenuName } from '../utils/resolveMenuName';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Title, Text } = Typography;

function useMenuConfigI18n() {
  return useI18n('menu-config');
}

function getMenuTypeLabels(t: (key: string) => string): Record<string, { label: string; color: string }> {
  return {
    directory: { label: t('directory'), color: 'blue' },
    menu: { label: t('menu'), color: 'green' },
    action: { label: t('action'), color: 'orange' },
  };
}

function getLinkTypeLabels(t: (key: string) => string): Record<string, string> {
  return {
    internal: t('internal'),
    iframe: t('iframe'),
  };
}

function getMenuIcon(item: MenuItem) {
  switch (item.menu_type) {
    case 'directory': return resolveIcon(item.icon || 'FolderOutlined');
    case 'action': return resolveIcon(item.icon || 'ThunderboltOutlined');
    default: return resolveIcon(item.icon || 'FileOutlined');
  }
}

function toTreeData(items: MenuItem[]): TreeDataNode[] {
  return items.map((item) => ({
    key: item.id,
    title: item.name,
    // 图标统一在 TreeNodeTitle 中渲染，避免与 Tree 的 showIcon 重复
    children: item.children ? toTreeData(item.children) : [],
  }));
}

function flattenTree(items: MenuItem[]): MenuItem[] {
  const result: MenuItem[] = [];
  const walk = (nodes: MenuItem[]) => {
    nodes.forEach((n) => {
      result.push(n);
      if (n.children?.length) walk(n.children);
    });
  };
  walk(items);
  return result;
}

function TreeNodeTitle({
  item,
  onAddChild,
  onEdit,
  onDelete,
}: {
  item: MenuItem;
  onAddChild: (item: MenuItem) => void;
  onEdit: (item: MenuItem) => void;
  onDelete: (id: string) => void;
}) {
  const { t } = useMenuConfigI18n();
  const labels = useMemo(() => getMenuTypeLabels(t), [t]);

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        width: '100%',
        gap: 8,
      }}
    >
      <span style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
        {getMenuIcon(item)}
        <span style={{ fontWeight: 500 }}>{resolveMenuName(t, item.name)}</span>
        <Tag
          style={{ fontSize: 11, flexShrink: 0 }}
          color={labels[item.menu_type]?.color || 'default'}
        >
          {labels[item.menu_type]?.label || item.menu_type}
        </Tag>
        {!item.is_active && (
          <Tag color="default" style={{ fontSize: 11, flexShrink: 0 }}>{t('inactive')}</Tag>
        )}
        {!item.is_visible && item.menu_type === 'menu' && (
          <Tag color="default" style={{ fontSize: 11, flexShrink: 0 }}>{t('hidden')}</Tag>
        )}
        {/* 权限码已从树节点中移除，避免显示ID/code；详情面板仍保留 */}
      </span>
      <span onClick={(e) => e.stopPropagation()}>
        {item.menu_type !== 'action' && (
          <Tooltip title={t('addChild')}>
            <Button type="text" size="small" icon={<PlusOutlined />} onClick={() => onAddChild(item)} />
          </Tooltip>
        )}
        <Tooltip title={t('edit')}>
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => onEdit(item)} />
        </Tooltip>
        <Popconfirm title={t('confirmDelete')} onConfirm={() => onDelete(item.id)}>
          <Tooltip title={t('delete')}>
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Tooltip>
        </Popconfirm>
      </span>
    </div>
  );
}

export function MenuConfigPage() {
  const { t } = useMenuConfigI18n();
  const MENU_TYPE_LABELS = useMemo(() => getMenuTypeLabels(t), [t]);
  const LINK_TYPE_LABELS = useMemo(() => getLinkTypeLabels(t), [t]);

  const [activeTab, setActiveTab] = useState<'menu' | 'role'>('menu');

  /* ── 菜单管理状态 ── */
  const [treeData, setTreeData] = useState<MenuItem[]>([]);
  const [flatItems, setFlatItems] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<MenuItem | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<MenuItem | null>(null);
  const [parentId, setParentId] = useState<string | null>(null);
  const [form] = Form.useForm();

  /* ── 角色权限状态 ── */
  const [roles, setRoles] = useState<RoleSummary[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState<string>('');
  const [roleMenuIds, setRoleMenuIds] = useState<string[]>([]);
  const [roleLoading, setRoleLoading] = useState(false);
  const [roleSaving, setRoleSaving] = useState(false);

  /* ── 加载菜单树 ── */
  const loadTree = useCallback(async () => {
    setLoading(true);
    try {
      const data = await menuConfigApi.getFullTree();
      setTreeData(data.tree || []);
      const flat = flattenTree(data.tree || []);
      setFlatItems(flat);
      if (selectedNode) {
        const stillExists = flat.find((i) => i.id === selectedNode.id);
        if (!stillExists) setSelectedNode(null);
      }
    } catch (e: any) {
      message.error(t('loadMenuTreeFailed') + ': ' + (e.message || e));
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── 加载角色列表（从 /api/roles） ── */
  const loadRoles = useCallback(async () => {
    try {
      const rolesData = await listRoles();
      const summaries: RoleSummary[] = rolesData.map((r) => ({
        id: r.id,
        name: r.name,
        description: r.description,
      }));
      setRoles(summaries);
      if (summaries.length > 0 && !selectedRoleId) {
        setSelectedRoleId(summaries[0].id);
      }
    } catch (e: any) {
      console.warn(t('loadRoleListFailed') + ' /api/roles:', e.message);
      message.warning(t('loadRoleListFailed'));
    }
  }, [selectedRoleId, t]);

  useEffect(() => { loadTree(); }, [loadTree]);
  useEffect(() => { loadRoles(); }, [loadRoles]);

  /* ── 创建/编辑菜单项 ── */
  const handleCreate = (parent?: string, menuType?: string) => {
    setEditingItem(null);
    setParentId(parent || null);
    form.resetFields();
    form.setFieldsValue({
      parent_id: parent || undefined,
      menu_type: menuType || 'menu',
      link_type: 'internal',
      icon: 'AppstoreOutlined',
      sort_order: 0,
      is_active: true,
      is_visible: true,
    });
    setModalOpen(true);
  };

  const handleEdit = (item: MenuItem) => {
    setEditingItem(item);
    setParentId(item.parent_id);
    form.setFieldsValue({
      ...item,
      parent_id: item.parent_id || undefined,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (!values.parent_id) values.parent_id = null;

      if (editingItem) {
        await menuConfigApi.updateItem(editingItem.id, values);
        message.success(t('updateSuccess'));
      } else {
        await menuConfigApi.createItem(values);
        message.success(t('createSuccess'));
      }
      setModalOpen(false);
      loadTree();
    } catch (e: any) {
      if (e.errorFields) return;
      message.error(t('saveFailed') + ': ' + (e.message || e));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await menuConfigApi.deleteItem(id);
      message.success(t('deleteSuccess'));
      setSelectedNode(null);
      loadTree();
    } catch (e: any) {
      message.error(t('deleteFailed') + ': ' + (e.message || e));
    }
  };

  /* ── 角色菜单权限 ── */
  const loadRoleMenus = useCallback(async (roleId: string) => {
    if (!roleId) return;
    setRoleLoading(true);
    try {
      const data = await menuConfigApi.getRoleMenus(roleId);
      setRoleMenuIds(data.menu_ids || []);
    } catch (e: any) {
      message.error(t('loadRoleMenuPermissionFailed') + ': ' + (e.message || e));
      setRoleMenuIds([]);
    } finally {
      setRoleLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (activeTab === 'role' && selectedRoleId) {
      loadRoleMenus(selectedRoleId);
    }
  }, [activeTab, selectedRoleId, loadRoleMenus]);

  const handleSaveRoleMenus = async () => {
    setRoleSaving(true);
    try {
      await menuConfigApi.setRoleMenus(selectedRoleId, roleMenuIds);
      message.success(t('roleMenuPermissionSaved'));
    } catch (e: any) {
      message.error(t('saveFailed') + ': ' + (e.message || e));
    } finally {
      setRoleSaving(false);
    }
  };

  const handleRoleMenuCheck = (keys: string[]) => {
    setRoleMenuIds(keys);
  };

  /* ── 树节点 ── */
  const handleTreeSelect = (keys: React.Key[]) => {
    if (keys.length === 0) {
      setSelectedNode(null);
      return;
    }
    const found = flatItems.find((i) => i.id === keys[0]);
    setSelectedNode(found || null);
  };

  const treeNodes = useMemo(() => toTreeData(treeData), [treeData]);

  const menuTreeTitleRender = (node: TreeDataNode) => {
    const item = flatItems.find((i) => i.id === node.key);
    if (!item) return node.title as React.ReactNode;
    return (
      <TreeNodeTitle
        item={item}
        onAddChild={(it) => handleCreate(
          it.id,
          it.menu_type === 'directory' ? 'menu' : 'action',
        )}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />
    );
  };

  return (
    <div style={{ padding: 24, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4} style={{ margin: 0 }}>{t('menuAndPermissionConfig')}</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => { loadTree(); loadRoles(); }} loading={loading}>
            {t('refresh')}
          </Button>
          {activeTab === 'menu' && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => handleCreate()}>
              {t('createTopLevelMenu')}
            </Button>
          )}
        </Space>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as 'menu' | 'role')}
        items={[
          { key: 'menu', label: t('menuManagement') },
          { key: 'role', label: t('rolePermissionAssignment') },
        ]}
        style={{ marginBottom: 16 }}
      />

      {activeTab === 'menu' ? (
        <div style={{ flex: 1, display: 'flex', gap: 16, minHeight: 0 }}>
          {/* 左侧菜单树 */}
          <Card
            title={t('menuTree')}
            size="small"
            style={{ width: 520, flexShrink: 0, display: 'flex', flexDirection: 'column' }}
            bodyStyle={{ padding: 8, overflow: 'auto', flex: 1 }}
          >
            {loading ? (
              <div style={{ textAlign: 'center', padding: 48 }}>
                <Text type="secondary">{t('loadingMenuTree')}</Text>
              </div>
            ) : treeNodes.length > 0 ? (
              <Tree
                treeData={treeNodes}
                showLine
                defaultExpandAll
                selectedKeys={selectedNode ? [selectedNode.id] : []}
                onSelect={handleTreeSelect}
                titleRender={menuTreeTitleRender}
                style={{ minWidth: 420 }}
              />
            ) : (
              <Empty description={t('emptyMenuHint')} />
            )}
          </Card>

          {/* 右侧详情 */}
          <Card
            title={selectedNode ? resolveMenuName(t, selectedNode.name) : t('menuDetails')}
            size="small"
            style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            bodyStyle={{ overflow: 'auto', flex: 1 }}
          >
            {selectedNode ? (
              <>
                <Descriptions column={2} size="small" bordered>
                  <Descriptions.Item label={t('name')}>{resolveMenuName(t, selectedNode.name)}</Descriptions.Item>
                  <Descriptions.Item label={t('permissionCode')}>
                    <Text code>{selectedNode.code}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('type')}>
                    <Tag color={MENU_TYPE_LABELS[selectedNode.menu_type]?.color}>
                      {MENU_TYPE_LABELS[selectedNode.menu_type]?.label}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('linkType')}>
                    {selectedNode.menu_type === 'menu'
                      ? LINK_TYPE_LABELS[selectedNode.link_type] || selectedNode.link_type
                      : '-'}
                  </Descriptions.Item>
                  {selectedNode.path && (
                    <Descriptions.Item label={t('routePath')} span={2}>
                      <Text code>{selectedNode.path}</Text>
                    </Descriptions.Item>
                  )}
                  {selectedNode.url && (
                    <Descriptions.Item label={t('iframeUrl')} span={2}>
                      <Text code>{selectedNode.url}</Text>
                    </Descriptions.Item>
                  )}
                  <Descriptions.Item label={t('icon')}>
                    <Space>
                      {getMenuIcon(selectedNode)}
                      <Text type="secondary">{selectedNode.icon}</Text>
                    </Space>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('sortOrder')}>{selectedNode.sort_order}</Descriptions.Item>
                  <Descriptions.Item label={t('active')}>
                    <Badge status={selectedNode.is_active ? 'success' : 'default'} text={selectedNode.is_active ? t('yes') : t('no')} />
                  </Descriptions.Item>
                  <Descriptions.Item label={t('visible')}>
                    <Badge status={selectedNode.is_visible ? 'success' : 'default'} text={selectedNode.is_visible ? t('yes') : t('no')} />
                  </Descriptions.Item>
                  <Descriptions.Item label={t('description')} span={2}>
                    {selectedNode.description || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="ID" span={2}>
                    <Text type="secondary">{selectedNode.id}</Text>
                  </Descriptions.Item>
                </Descriptions>
                <Divider />
                <Space>
                  <Button icon={<EditOutlined />} onClick={() => handleEdit(selectedNode)}>{t('edit')}</Button>
                  <Popconfirm title={t('confirmDelete')} onConfirm={() => handleDelete(selectedNode.id)}>
                    <Button danger icon={<DeleteOutlined />}>{t('delete')}</Button>
                  </Popconfirm>
                </Space>
              </>
            ) : (
              <Empty description={t('selectMenuItemHint')} />
            )}
          </Card>
        </div>
      ) : (
        <RoleMenuAssigner
          roles={roles}
          selectedRoleId={selectedRoleId}
          onSelectRole={setSelectedRoleId}
          menuTreeItems={flatItems}
          menuTreeNode={treeNodes}
          checkedMenuIds={roleMenuIds}
          onCheck={handleRoleMenuCheck}
          onSave={handleSaveRoleMenus}
          roleLoading={roleLoading}
          roleSaving={roleSaving}
          onReset={() => loadRoleMenus(selectedRoleId)}
        />
      )}

      {/* ── 创建/编辑 Modal ── */}
      <Modal
        title={editingItem ? t('editMenuItem') : t('createMenuItem')}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="parent_id" label={t('parentMenu')}>
            <Select
              allowClear
              placeholder={t('rootDirectory')}
              options={[
                { value: '__root__', label: t('rootDirectory') },
                ...flatItems
                  .filter((i) => i.menu_type !== 'action' && i.id !== editingItem?.id)
                  .map((i) => ({
                    value: i.id,
                    label: `${i.name} (${MENU_TYPE_LABELS[i.menu_type]?.label})`,
                  })),
              ]}
              onChange={(val) => {
                if (val === '__root__') form.setFieldValue('parent_id', null);
              }}
            />
          </Form.Item>

          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="name" label={t('name')} rules={[{ required: true }]} style={{ flex: 1 }}>
              <Input placeholder={t('namePlaceholder')} />
            </Form.Item>
            <Form.Item name="code" label={t('permissionCode')} rules={[{ required: true }]} style={{ flex: 1 }}>
              <Input placeholder={t('permissionCodePlaceholder')} />
            </Form.Item>
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="menu_type" label={t('type')} rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select
                options={[
                  { value: 'directory', label: t('directoryDescription') },
                  { value: 'menu', label: t('menuDescription') },
                  { value: 'action', label: t('actionDescription') },
                ]}
              />
            </Form.Item>
            <Form.Item name="link_type" label={t('linkType')} style={{ flex: 1 }}>
              <Select
                options={[
                  { value: 'internal', label: t('internal') },
                  { value: 'iframe', label: t('iframe') },
                ]}
              />
            </Form.Item>
          </div>

          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.link_type !== cur.link_type || prev.menu_type !== cur.menu_type}>
            {({ getFieldValue }) => {
              const linkType = getFieldValue('link_type');
              const menuType = getFieldValue('menu_type');
              if (menuType === 'menu' && linkType === 'internal') {
                return (
                  <Form.Item name="path" label={t('routePath')}>
                    <Input placeholder={t('routePathPlaceholder')} />
                  </Form.Item>
                );
              }
              if (menuType === 'menu' && linkType === 'iframe') {
                return (
                  <>
                    <Form.Item name="path" label={t('routePath')}>
                      <Input placeholder={t('iframePathPlaceholder')} />
                    </Form.Item>
                    <Form.Item name="url" label={t('iframeUrl')}>
                      <Input placeholder={t('iframeUrlPlaceholder')} />
                    </Form.Item>
                  </>
                );
              }
              return null;
            }}
          </Form.Item>

          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="icon" label={t('icon')} style={{ flex: 1 }}>
              <Select
                showSearch
                options={ICON_OPTIONS.map((o) => ({
                  value: o.value,
                  label: `${o.label} (${o.value})`,
                }))}
              />
            </Form.Item>
            <Form.Item name="sort_order" label={t('sortOrder')} style={{ flex: 1 }}>
              <InputNumber min={0} max={999} style={{ width: '100%' }} />
            </Form.Item>
          </div>

          <div style={{ display: 'flex', gap: 24 }}>
            <Form.Item name="is_active" label={t('active')} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="is_visible" label={t('sidebarVisible')} valuePropName="checked">
              <Switch />
            </Form.Item>
          </div>

          <Form.Item name="description" label={t('description')}>
            <Input.TextArea rows={2} placeholder={t('descriptionPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
