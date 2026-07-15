/**
 * 层级结构树（Iter 1 用 AntD Tree 低成本实现，Iter 2 升级为 AntV G6）
 * 上方：工具栏（新建 is_a / 新建 part_of / 删除 / 刷新）
 * 中间：Tree 树形展示（树节点后缀展示置信度）
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  Tree,
  Button,
  Space,
  App,
  Tooltip,
  Modal,
  Form,
  Select,
  InputNumber,
  Empty,
  Tag,
  Popconfirm,
  Typography,
} from 'antd';
import type { DataNode } from 'antd/es/tree';
import {
  DeleteOutlined,
  ReloadOutlined,
  ShareAltOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import type {
  UslHierarchy,
  UslTerm,
  HierarchyRelType,
} from '../types';
import { HIERARCHY_REL_OPTIONS } from '../types';
import {
  listHierarchies,
  createHierarchy,
  deleteHierarchy,
  listTerms,
} from '../services/uslApi';
import { useSemanticAdminStore } from '../store/useSemanticAdminStore';
import { useUslPermissions } from '../hooks/useUslPermissions';

const { Text } = Typography;

interface HierarchyFormValues {
  rel_type: HierarchyRelType;
  parent_term: string;
  child_term: string;
  confidence: number;
}

export function HierarchyTree() {
  const { message } = App.useApp();
  const { canWrite } = useUslPermissions();
  const currentDomain = useSemanticAdminStore((s) => s.currentDomain);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<UslHierarchy[]>([]);
  const [termOptions, setTermOptions] = useState<Array<{ label: string; value: string }>>([]);
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
  const [formOpen, setFormOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<HierarchyFormValues>();

  const fetchData = async () => {
    if (!currentDomain) return;
    setLoading(true);
    try {
      const [h, t] = await Promise.all([
        listHierarchies(currentDomain.code),
        listTerms(currentDomain.code, { page: 1, page_size: 500 }).catch(() => ({ items: [] as UslTerm[] })),
      ]);
      const list = Array.isArray(h) ? h : [];
      setItems(list);
      const termList: UslTerm[] = 'items' in t ? (t.items as UslTerm[]) : [];
      setTermOptions(
        termList.map((tm) => ({
          label: `${tm.canonical}（${tm.en || '-'}）`,
          value: tm.canonical,
        })),
      );
      // 默认展开根节点的直接子
      const roots = findAllRoots(list);
      setExpandedKeys(roots);
    } catch (err) {
      console.warn('[HierarchyTree] fetch failed:', err);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentDomain?.code]);

  /** 构建树：根据 parent_term -> child_term 关系组装 AntD Tree DataNode */
  const treeData: DataNode[] = useMemo(() => {
    return buildTreeFromHierarchies(items);
  }, [items]);

  const selectedKeysState = useState<React.Key[]>([]);
  const selectedKey = selectedKeysState[0][0];
  const selectedHierarchy = useMemo<UslHierarchy | null>(() => {
    if (!selectedKey) return null;
    // key 格式：`node-${canonical}` for 纯术语；`edge-${id}` for 单独边
    const sk = String(selectedKey);
    if (sk.startsWith('edge-')) {
      return items.find((h) => h.id === sk.slice(5)) || null;
    }
    return null;
  }, [selectedKey, items]);

  const handleOpenCreate = (relType: HierarchyRelType) => {
    form.resetFields();
    form.setFieldsValue({
      rel_type: relType,
      confidence: 0.8,
    });
    setFormOpen(true);
  };

  const handleDeleteSelected = async () => {
    if (!selectedHierarchy?.id) return;
    try {
      await deleteHierarchy(selectedHierarchy.id);
      message.success('层级关系已删除');
      void fetchData();
    } catch (err) {
      message.error(`删除失败：${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleSubmit = async () => {
    if (!currentDomain) return;
    try {
      const v = await form.validateFields();
      setSubmitting(true);
      await createHierarchy({
        domain_id: currentDomain.code,
        rel_type: v.rel_type,
        parent_term: v.parent_term,
        child_term: v.child_term,
        confidence: Number.isFinite(v.confidence) ? v.confidence : 0.5,
        provenance: 'manual_usl_admin',
      });
      message.success('层级关系已创建');
      setFormOpen(false);
      void fetchData();
    } catch (err) {
      if (err instanceof Error && !String(err.message).includes('validate')) {
        message.error(err.message || '提交失败');
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (!currentDomain) {
    return (
      <div style={{ padding: 48, textAlign: 'center', color: '#8c8c8c', background: '#fafafa', borderRadius: 6 }}>
        请先选择语义域
      </div>
    );
  }

  return (
    <div>
      <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }} wrap>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={() => void fetchData()}>
            刷新
          </Button>
          <Tooltip title={canWrite ? '' : '需要 admin / schema_auditor'}>
            <Button
              icon={<ShareAltOutlined />}
              type="primary"
              ghost
              disabled={!canWrite}
              onClick={() => handleOpenCreate('is_a')}
            >
              新建 is_a 继承
            </Button>
          </Tooltip>
          <Tooltip title={canWrite ? '' : '需要 admin / schema_auditor'}>
            <Button
              icon={<ApiOutlined />}
              type="primary"
              ghost
              disabled={!canWrite}
              onClick={() => handleOpenCreate('part_of')}
            >
              新建 part_of 组成
            </Button>
          </Tooltip>
          <Popconfirm
            title="删除选中的层级边？"
            disabled={!selectedHierarchy?.id || !canWrite}
            okButtonProps={{ danger: true }}
            onConfirm={handleDeleteSelected}
            okText="删除"
            cancelText="取消"
          >
            <Button
              danger
              icon={<DeleteOutlined />}
              disabled={!selectedHierarchy?.id || !canWrite}
            >
              删除选中边
            </Button>
          </Popconfirm>
        </Space>
        <Space>
          <Tag color="geekblue">共 {items.length} 条关系</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Iter 1：AntD Tree 展示；Iter 2 将升级为 AntV G6 可拖拽图谱
          </Text>
        </Space>
      </Space>

      <div
        style={{
          minHeight: 360,
          border: '1px dashed #d9d9d9',
          borderRadius: 6,
          padding: 16,
          background: '#fafafa',
        }}
      >
        {treeData.length === 0 ? (
          <Empty
            description={
              <div style={{ textAlign: 'center' }}>
                <Text type="secondary">当前域无层级数据</Text>
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  点击「新建 is_a 继承」或「新建 part_of 组成」添加，也可从 OL 流水线审核台写回
                </Text>
              </div>
            }
          />
        ) : (
          <Tree
            showLine={{ showLeafIcon: false }}
            blockNode
            multiple={false}
            selectable
            checkable={false}
            expandedKeys={expandedKeys}
            onExpand={(keys) => setExpandedKeys(keys)}
            selectedKeys={selectedKeysState[0]}
            onSelect={(keys) => selectedKeysState[1](keys)}
            treeData={treeData}
            loading={loading}
          />
        )}
      </div>

      <Modal
        title="新建层级关系"
        open={formOpen}
        onCancel={() => setFormOpen(false)}
        onOk={handleSubmit}
        okText="创建"
        cancelText="取消"
        okButtonProps={{ disabled: !canWrite, loading: submitting }}
        destroyOnHidden
        width={480}
      >
        <Form form={form} layout="vertical" preserve={false} requiredMark="optional">
          <Form.Item
            label="关系类型"
            name="rel_type"
            rules={[{ required: true, message: '必选' }]}
          >
            <Select options={HIERARCHY_REL_OPTIONS} disabled={!canWrite} />
          </Form.Item>
          <Space.Compact style={{ width: '100%' }}>
            <Form.Item
              label="父术语（上位）"
              name="parent_term"
              style={{ width: '50%' }}
              rules={[{ required: true, message: '必选' }]}
            >
              <Select
                showSearch
                options={termOptions}
                disabled={!canWrite}
                filterOption={(input, opt) =>
                  !!(opt?.label && String(opt.label).toLowerCase().includes(input.toLowerCase()))
                }
              />
            </Form.Item>
            <Form.Item
              label="子术语（下位）"
              name="child_term"
              style={{ width: '50%' }}
              rules={[{ required: true, message: '必选' }]}
            >
              <Select
                showSearch
                options={termOptions}
                disabled={!canWrite}
                filterOption={(input, opt) =>
                  !!(opt?.label && String(opt.label).toLowerCase().includes(input.toLowerCase()))
                }
              />
            </Form.Item>
          </Space.Compact>
          <Form.Item
            label="置信度（0-1）"
            name="confidence"
            rules={[
              { required: true, message: '必填' },
              {
                validator: (_, v: number) =>
                  v >= 0 && v <= 1 ? Promise.resolve() : Promise.reject(new Error('必须在 0 到 1 之间')),
              },
            ]}
          >
            <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} disabled={!canWrite} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

// ========== 纯函数工具（Tree 构造） ==========

/** 找所有作为 parent 但从不作为 child 的术语 canonical，作为扩展根 */
function findAllRoots(list: UslHierarchy[]): string[] {
  const childSet = new Set(list.map((h) => h.child_term));
  const roots = list
    .filter((h) => !childSet.has(h.parent_term))
    .map((h) => `node-${h.parent_term}`);
  return Array.from(new Set(roots));
}

function buildTreeFromHierarchies(list: UslHierarchy[]): DataNode[] {
  // Step 1: 每个术语的直接子节点（按 rel_type 分组）
  const parentToChildren: Map<string, Array<{ rel: UslHierarchy; relLabel: string }>> = new Map();
  const allTerms: Set<string> = new Set();
  list.forEach((h) => {
    const relLabel = h.rel_type === 'is_a' ? 'is_a' : 'part_of';
    allTerms.add(h.parent_term);
    allTerms.add(h.child_term);
    if (!parentToChildren.has(h.parent_term)) {
      parentToChildren.set(h.parent_term, []);
    }
    parentToChildren.get(h.parent_term)!.push({ rel: h, relLabel });
  });

  // Step 2: 找根（从未作为 child 的术语）
  const children = new Set(list.map((h) => h.child_term));
  const roots: string[] = [];
  allTerms.forEach((t) => {
    if (!children.has(t)) roots.push(t);
  });
  // 若有环，roots 为空；退化为列表展示
  const realRoots = roots.length > 0 ? roots : Array.from(allTerms);

  // Step 3: 递归组装 Tree DataNode
  const visited = new Set<string>();
  function toNode(canonical: string, depth: number): DataNode {
    const key = `node-${canonical}`;
    if (visited.has(key) && depth > 8) {
      return { key: `${key}-cycle-${Math.random()}`, title: (
        <span style={{ color: '#ff4d4f' }}>{canonical} <Tag color="red">CYCLE</Tag></span>
      ) };
    }
    visited.add(key);
    const childrenEntries = parentToChildren.get(canonical) || [];
    return {
      key,
      title: (
        <Space size="small">
          <Tag color="geekblue">{canonical}</Tag>
        </Space>
      ),
      children: childrenEntries.map(({ rel, relLabel }) => ({
        key: `edge-${rel.id || `${rel.parent_term}-${rel.child_term}-${Math.random()}`}`,
        title: (
          <Space size="small">
            <Tag color={relLabel === 'is_a' ? 'blue' : 'green'} style={{ marginRight: 8 }}>
              {relLabel} <span style={{ opacity: 0.5 }}>· conf {(rel.confidence ?? 1).toFixed(2)}</span>
            </Tag>
            {toNode(rel.child_term, depth + 1).title as React.ReactNode}
          </Space>
        ),
        children: (() => {
          const childNode = toNode(rel.child_term, depth + 1);
          return childNode.children && childNode.children.length > 0 ? childNode.children : undefined;
        })(),
      })),
    };
  }

  return realRoots.map((r) => toNode(r, 0));
}
