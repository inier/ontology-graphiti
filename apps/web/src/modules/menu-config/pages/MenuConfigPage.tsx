import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Card, Tree, Button, Space, Tag, Typography, Modal, Form, Input,
  Select, InputNumber, Switch, message, Popconfirm, Tooltip, Tabs,
  Empty, Badge, Descriptions, Divider,
} from 'antd';
import type { TreeDataNode } from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
  
  ReloadOutlined, SafetyOutlined,
} from '@ant-design/icons';
import { menuConfigApi, type MenuItem } from '../services/menuConfigApi';
import { RoleMenuAssigner, type RoleSummary } from '../components/RoleMenuAssigner';
import { resolveIcon, ICON_OPTIONS } from '../utils/iconResolver';
import { resolveMenuName } from '../utils/resolveMenuName';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { useAuthStore } from '@/modules/shared/stores/authStore';

const { Title, Text } = Typography;

function useMenuConfigI18n() {
  return useI18n('menu-config');
}

function getMenuTypeLabels(t: (key: string) => string): Record<string, { label: string; color: string }> {
  return {
    directory: { label: t('目录'), color: 'blue' },
    menu: { label: t('菜单'), color: 'green' },
    action: { label: t('操作'), color: 'orange' },
  };
}

function getLinkTypeLabels(t: (key: string) => string): Record<string, string> {
  return {
    internal: t('内部路由'),
    iframe: t('外部 iframe'),
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
          <Tag color="default" style={{ fontSize: 11, flexShrink: 0 }}>{t('禁用')}</Tag>
        )}
        {!item.is_visible && item.menu_type === 'menu' && (
          <Tag color="default" style={{ fontSize: 11, flexShrink: 0 }}>{t('隐藏')}</Tag>
        )}
        {/* 权限码已从树节点中移除，避免显示ID/code；详情面板仍保留 */}
      </span>
      <span onClick={(e) => e.stopPropagation()}>
        {item.menu_type !== 'action' && (
          <Tooltip title={t('添加子项')}>
            <Button type="text" size="small" icon={<PlusOutlined />} onClick={() => onAddChild(item)} />
          </Tooltip>
        )}
        <Tooltip title={t('编辑')}>
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => onEdit(item)} />
        </Tooltip>
        <Popconfirm title={t('确认删除？子节点也会一并删除')} onConfirm={() => onDelete(item.id)}>
          <Tooltip title={t('删除')}>
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
  const [, setParentId] = useState<string | null>(null);
  const [form] = Form.useForm();

  /* ── 角色权限状态 ── */
  const [roles, setRoles] = useState<RoleSummary[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState<string>('');
  const [roleMenuIds, setRoleMenuIds] = useState<string[]>([]);
  const [roleLoading, setRoleLoading] = useState(false);
  const [roleSaving, setRoleSaving] = useState(false);

  /* ── 恢复默认菜单（管理员专属） ── */
  const isAdmin = useAuthStore((s) => s.user?.global_role === 'admin');
  const [initModalOpen, setInitModalOpen] = useState(false);
  const [initLoading, setInitLoading] = useState(false);

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
    } catch (e) {
      const errMessage = e instanceof Error ? e.message : String(e);
      message.error(t('加载菜单树失败') + ': ' + (errMessage || e));
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── 加载角色列表（内置全局角色，与 JWT role 对齐） ── */
  const loadRoles = useCallback(async () => {
    try {
      const data = await menuConfigApi.getGlobalRoles();
      const summaries: RoleSummary[] = (data.roles || []).map((r) => ({
        id: r.id,
        name: r.name,
        description: r.description,
      }));
      setRoles(summaries);
      // 默认选中第一个非 admin 角色（admin 是全量菜单，配置无意义）
      setSelectedRoleId((prev) => {
        if (prev) return prev;
        return (summaries.find((r) => r.id !== 'admin') || summaries[0])?.id || '';
      });
    } catch (e: unknown) {
      const errMessage = e instanceof Error ? e.message : String(e);
      console.warn(t('加载角色列表失败') + ' /api/menu-config/global-roles:', errMessage);
      message.warning(t('加载角色列表失败'));
    }
  }, [t]);

  useEffect(() => {   void (async () => {
    loadTree();
  })(); }, [loadTree]);
  useEffect(() => {   void (async () => {
    loadRoles();
  })(); }, [loadRoles]);

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
        message.success(t('更新成功'));
      } else {
        await menuConfigApi.createItem(values);
        message.success(t('创建成功'));
      }
      setModalOpen(false);
      loadTree();
    } catch (e: unknown) {
      const errMessage = e instanceof Error ? e.message : String(e);
      if (e && typeof e === 'object' && 'errorFields' in e) return;
      message.error(t('保存失败') + ': ' + (errMessage || String(e)));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await menuConfigApi.deleteItem(id);
      message.success(t('已删除'));
      setSelectedNode(null);
      loadTree();
    } catch (e: unknown) {
      const errMessage = e instanceof Error ? e.message : String(e);
      message.error(t('删除失败') + ': ' + (errMessage || e));
    }
  };

  /* ── 角色菜单权限 ── */
  const loadRoleMenus = useCallback(async (roleId: string) => {
    if (!roleId) return;
    setRoleLoading(true);
    try {
      const data = await menuConfigApi.getRoleMenus(roleId);
      setRoleMenuIds(data.menu_ids || []);
    } catch (e: unknown) {
      const errMessage = e instanceof Error ? e.message : String(e);
      message.error(t('加载角色菜单权限失败') + ': ' + (errMessage || e));
      setRoleMenuIds([]);
    } finally {
      setRoleLoading(false);
    }
  }, [t]);

  useEffect(() => {
        void (async () => {
      if (activeTab === 'role' && selectedRoleId) {
        loadRoleMenus(selectedRoleId);
      }
    })();
  }, [activeTab, selectedRoleId, loadRoleMenus]);

  const handleSaveRoleMenus = async () => {
    setRoleSaving(true);
    try {
      await menuConfigApi.setRoleMenus(selectedRoleId, roleMenuIds);
      message.success(t('角色菜单权限已保存'));
    } catch (e: unknown) {
      const errMessage = e instanceof Error ? e.message : String(e);
      message.error(t('保存失败') + ': ' + (errMessage || e));
    } finally {
      setRoleSaving(false);
    }
  };

  const handleRoleMenuCheck = (keys: string[]) => {
    setRoleMenuIds(keys);
  };

  /* ── 恢复默认菜单（幂等，仅管理员可见按钮，后端另有 403 校验） ── */
  const handleInitDefault = async () => {
    setInitLoading(true);
    try {
      const res = await menuConfigApi.initDefault();
      message.success(
        `${t('恢复完成')}：created=${res.created ?? 0}, skipped=${res.skipped ?? 0}, role_grants=${res.role_grants ?? 0}`,
      );
      setInitModalOpen(false);
      loadTree();
      loadRoles();
    } catch (e: unknown) {
      const errMessage = e instanceof Error ? e.message : String(e);
      message.error(t('恢复失败') + ': ' + (errMessage || e));
    } finally {
      setInitLoading(false);
    }
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
        <Title level={4} style={{ margin: 0 }}>{t('菜单与权限配置')}</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => { loadTree(); loadRoles(); }} loading={loading}>
            {t('refresh')}
          </Button>
          {isAdmin && (
            <Tooltip title={t('幂等恢复默认菜单树与角色默认授权，不会覆盖自定义菜单')}>
              <Button icon={<SafetyOutlined />} onClick={() => setInitModalOpen(true)}>
                {t('恢复默认菜单')}
              </Button>
            </Tooltip>
          )}
          {activeTab === 'menu' && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => handleCreate()}>
              {t('新建顶级菜单')}
            </Button>
          )}
        </Space>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as 'menu' | 'role')}
        items={[
          { key: 'menu', label: t('菜单管理') },
          { key: 'role', label: t('角色权限分配') },
        ]}
        style={{ marginBottom: 16 }}
      />

      {activeTab === 'menu' ? (
        <div style={{ flex: 1, display: 'flex', gap: 16, minHeight: 0 }}>
          {/* 左侧菜单树 */}
          <Card
            title={t('菜单树')}
            size="small"
            style={{ width: 520, flexShrink: 0, display: 'flex', flexDirection: 'column' }}
            styles={{ body: { padding: 8, overflow: 'auto', flex: 1 } }}
          >
            {loading ? (
              <div style={{ textAlign: 'center', padding: 48 }}>
                <Text type="secondary">{t('加载菜单树…')}</Text>
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
              <Empty description={t('暂无菜单项，点击右上角「新建顶级菜单」创建')} />
            )}
          </Card>

          {/* 右侧详情 */}
          <Card
            title={selectedNode ? resolveMenuName(t, selectedNode.name) : t('菜单详情')}
            size="small"
            style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            styles={{ body: { overflow: 'auto', flex: 1 }}}
          >
            {selectedNode ? (
              <>
                <Descriptions column={2} bordered>
                  <Descriptions.Item label={t('name')}>{resolveMenuName(t, selectedNode.name)}</Descriptions.Item>
                  <Descriptions.Item label={t('权限码')}>
                    <Text code>{selectedNode.code}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('type')}>
                    <Tag color={MENU_TYPE_LABELS[selectedNode.menu_type]?.color}>
                      {MENU_TYPE_LABELS[selectedNode.menu_type]?.label}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('链接类型')}>
                    {selectedNode.menu_type === 'menu'
                      ? LINK_TYPE_LABELS[selectedNode.link_type] || selectedNode.link_type
                      : '-'}
                  </Descriptions.Item>
                  {selectedNode.path && (
                    <Descriptions.Item label={t('路由路径')} span={2}>
                      <Text code>{selectedNode.path}</Text>
                    </Descriptions.Item>
                  )}
                  {selectedNode.url && (
                    <Descriptions.Item label={t('iframe URL')} span={2}>
                      <Text code>{selectedNode.url}</Text>
                    </Descriptions.Item>
                  )}
                  <Descriptions.Item label={t('icon')}>
                    <Space>
                      {getMenuIcon(selectedNode)}
                      <Text type="secondary">{selectedNode.icon}</Text>
                    </Space>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('排序')}>{selectedNode.sort_order}</Descriptions.Item>
                  <Descriptions.Item label={t('启用')}>
                    <Badge status={selectedNode.is_active ? 'success' : 'default'} text={selectedNode.is_active ? t('是') : t('否')} />
                  </Descriptions.Item>
                  <Descriptions.Item label={t('可见')}>
                    <Badge status={selectedNode.is_visible ? 'success' : 'default'} text={selectedNode.is_visible ? t('是') : t('否')} />
                  </Descriptions.Item>
                  <Descriptions.Item label={t('描述')} span={2}>
                    {selectedNode.description || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="ID" span={2}>
                    <Text type="secondary">{selectedNode.id}</Text>
                  </Descriptions.Item>
                </Descriptions>
                <Divider />
                <Space>
                  <Button icon={<EditOutlined />} onClick={() => handleEdit(selectedNode)}>{t('编辑')}</Button>
                  <Popconfirm title={t('确认删除？子节点也会一并删除')} onConfirm={() => handleDelete(selectedNode.id)}>
                    <Button danger icon={<DeleteOutlined />}>{t('删除')}</Button>
                  </Popconfirm>
                </Space>
              </>
            ) : (
              <Empty description={t('选择左侧菜单项查看详情')} />
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

      {/* ── 恢复默认菜单确认 Modal（管理员专属） ── */}
      <Modal
        title={t('恢复默认菜单')}
        open={initModalOpen}
        onOk={handleInitDefault}
        onCancel={() => setInitModalOpen(false)}
        okText={t('确认恢复')}
        cancelText={t('取消')}
        okButtonProps={{ loading: initLoading, danger: true }}
        destroyOnHidden
      >
        <Text type="secondary">
          {t('将幂等写入默认菜单项，并为非 admin 全局角色补全默认授权。已存在的自定义菜单不会被覆盖。')}
        </Text>
      </Modal>

      {/* ── 创建/编辑 Modal ── */}
      <Modal
        title={editingItem ? t('编辑菜单项') : t('新建菜单项')}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        width={640}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="parent_id" label={t('父级菜单')}>
            <Select
              allowClear
              placeholder={t('根目录')}
              options={[
                { value: '__root__', label: t('根目录') },
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
              <Input placeholder={t('i18n key，如 menu.ontology.designer')} />
            </Form.Item>
            <Form.Item name="code" label={t('权限码')} rules={[{ required: true }]} style={{ flex: 1 }}>
              <Input placeholder={t('如 ontology:designer:view')} />
            </Form.Item>
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="menu_type" label={t('type')} rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select
                options={[
                  { value: 'directory', label: t('目录（可折叠分组）') },
                  { value: 'menu', label: t('菜单（可导航页面）') },
                  { value: 'action', label: t('操作（按钮/权限点）') },
                ]}
              />
            </Form.Item>
            <Form.Item name="link_type" label={t('链接类型')} style={{ flex: 1 }}>
              <Select
                options={[
                  { value: 'internal', label: t('内部路由') },
                  { value: 'iframe', label: t('外部 iframe') },
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
                  <Form.Item name="path" label={t('路由路径')}>
                    <Input placeholder={t('如：/users 或 /knowledge')} />
                  </Form.Item>
                );
              }
              if (menuType === 'menu' && linkType === 'iframe') {
                return (
                  <>
                    <Form.Item name="path" label={t('路由路径')}>
                      <Input placeholder={t('如：/minio-console')} />
                    </Form.Item>
                    <Form.Item name="url" label={t('iframe URL')}>
                      <Input placeholder={t('如：http://localhost:9001')} />
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
            <Form.Item name="sort_order" label={t('排序')} style={{ flex: 1 }}>
              <InputNumber min={0} max={999} style={{ width: '100%' }} />
            </Form.Item>
          </div>

          <div style={{ display: 'flex', gap: 24 }}>
            <Form.Item name="is_active" label={t('启用')} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="is_visible" label={t('侧边栏可见')} valuePropName="checked">
              <Switch />
            </Form.Item>
          </div>

          <Form.Item name="description" label={t('描述')}>
            <Input.TextArea rows={2} placeholder={t('菜单项说明')} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
