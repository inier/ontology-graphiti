/**
 * BranchList 组件 —— 本体分支列表 + 创建分支（FR-032 / T346）
 *
 * 顶部：搜索框 + "New Branch" 按钮
 * 表格列：Branch Name | Base Version | Created By | Created At | Status | Actions
 * 状态徽章：active / merged / archived / abandoned
 * 操作：Switch / Merge / View Diff / Archive / Delete
 * 创建分支 Modal：name + base_version_id + description
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Tag, Button, Space, Input, Modal, Form, Select, Popconfirm, Empty, Spin, Typography, message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined, ReloadOutlined, BranchesOutlined, SearchOutlined,
  CheckOutlined, MergeCellsOutlined, DiffOutlined, InboxOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { AdvancedTable } from '@/modules/shared';

const { Text, Title } = Typography;
const { TextArea } = Input;

export type BranchStatus = 'active' | 'merged' | 'archived' | 'abandoned';

export interface BranchInfo {
  branch_id: string;
  name: string;
  base_version_id?: string;
  base_version_label?: string;
  created_by: string;
  created_at: string;
  description?: string;
  status: BranchStatus;
  head_version_id?: string;
}

export interface BranchListProps {
  workspaceId?: string;
  onViewDiff?: (branch: BranchInfo) => void;
  onSelectBranch?: (branch: BranchInfo) => void;
}

const STATUS_META: Record<BranchStatus, { color: string; label: string }> = {
  active: { color: 'green', label: 'active' },
  merged: { color: 'blue', label: 'merged' },
  archived: { color: 'default', label: 'archived' },
  abandoned: { color: 'red', label: 'abandoned' },
};

export function BranchList({ workspaceId, onViewDiff, onSelectBranch }: BranchListProps) {
  const { t } = useI18n();
  const [branches, setBranches] = useState<BranchInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [versionOptions, setVersionOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [form] = Form.useForm();

  void workspaceId;

  const fetchBranches = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ branches: BranchInfo[] }>(
        `/api/ontology/branches${workspaceId ? `?workspace_id=${workspaceId}` : ''}`,
      );
      setBranches(data.branches || []);
    } catch (e) {
      message.error(`加载分支失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  const fetchVersions = useCallback(async () => {
    try {
      const data = await apiClient.get<{ versions: Array<{ version_id: string; version_number: number; changelog?: string }> }>(
        '/api/ontology/versions',
      );
      const options = (data.versions || []).map((v) => ({
        value: v.version_id,
        label: `v${v.version_number}${v.changelog ? ' — ' + v.changelog.slice(0, 30) : ''}`,
      }));
      setVersionOptions(options);
    } catch {
      // 非关键失败，忽略
      setVersionOptions([]);
    }
  }, []);

  useEffect(() => {
    void fetchBranches();
    void fetchVersions();
  }, [fetchBranches, fetchVersions]);

  const filtered = useMemo(() => {
    if (!searchText) return branches;
    const kw = searchText.toLowerCase();
    return branches.filter(
      (b) => b.name.toLowerCase().includes(kw) || b.created_by.toLowerCase().includes(kw),
    );
  }, [branches, searchText]);

  const handleCreate = useCallback(async () => {
    try {
      const values = await form.validateFields();
      setCreating(true);
      await apiClient.post('/api/ontology/branches', {
        ...values,
        workspace_id: workspaceId,
      });
      message.success('分支已创建');
      setCreateOpen(false);
      form.resetFields();
      void fetchBranches();
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) {
        // 表单校验错误
        return;
      }
      message.error(`创建失败: ${(e as Error).message}`);
    } finally {
      setCreating(false);
    }
  }, [form, workspaceId, fetchBranches]);

  const handleSwitch = useCallback(async (b: BranchInfo) => {
    try {
      await apiClient.post(`/api/ontology/branches/${b.branch_id}/switch`, {});
      message.success(`已切换到分支 ${b.name}`);
      onSelectBranch?.(b);
    } catch (e) {
      message.error(`切换失败: ${(e as Error).message}`);
    }
  }, [onSelectBranch]);

  const handleMerge = useCallback(async (b: BranchInfo) => {
    try {
      await apiClient.post(`/api/ontology/branches/${b.branch_id}/merge`, {});
      message.success(`分支 ${b.name} 已合并`);
      void fetchBranches();
    } catch (e) {
      message.error(`合并失败: ${(e as Error).message}`);
    }
  }, [fetchBranches]);

  const handleArchive = useCallback(async (b: BranchInfo) => {
    try {
      await apiClient.post(`/api/ontology/branches/${b.branch_id}/archive`, {});
      message.success('分支已归档');
      void fetchBranches();
    } catch (e) {
      message.error(`归档失败: ${(e as Error).message}`);
    }
  }, [fetchBranches]);

  const handleDelete = useCallback(async (b: BranchInfo) => {
    try {
      await apiClient.delete(`/api/ontology/branches/${b.branch_id}`);
      message.success('分支已删除');
      void fetchBranches();
    } catch (e) {
      message.error(`删除失败: ${(e as Error).message}`);
    }
  }, [fetchBranches]);

  const columns: ColumnsType<BranchInfo> = [
    {
      title: '分支名',
      dataIndex: 'name',
      key: 'name',
      render: (v: string, r) => (
        <Space size={4} orientation="vertical" style={{ lineHeight: 1.2 }}>
          <Space size={4}>
            <BranchesOutlined />
            <Text strong>{v}</Text>
          </Space>
          {r.description && <Text type="secondary" style={{ fontSize: 12 }}>{r.description}</Text>}
        </Space>
      ),
    },
    {
      title: '基于版本',
      dataIndex: 'base_version_label',
      key: 'base_version_label',
      width: 140,
      render: (v?: string, r?: BranchInfo) => v || (r?.base_version_id ? r.base_version_id.slice(0, 8) : '-'),
    },
    { title: '创建人', dataIndex: 'created_by', key: 'created_by', width: 130 },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (s: BranchStatus) => <Tag color={STATUS_META[s].color}>{STATUS_META[s].label}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 260,
      render: (_: unknown, r) => (
        <Space size={4} wrap>
          <Button
            size="small"
            type="link"
            icon={<CheckOutlined />}
            onClick={() => handleSwitch(r)}
            disabled={r.status !== 'active'}
          >
            Switch
          </Button>
          <Button
            size="small"
            type="link"
            icon={<MergeCellsOutlined />}
            onClick={() => handleMerge(r)}
            disabled={r.status !== 'active'}
          >
            Merge
          </Button>
          {onViewDiff && (
            <Button
              size="small"
              type="link"
              icon={<DiffOutlined />}
              onClick={() => onViewDiff(r)}
            >
              View Diff
            </Button>
          )}
          <Button
            size="small"
            type="link"
            icon={<InboxOutlined />}
            onClick={() => handleArchive(r)}
            disabled={r.status !== 'active'}
          >
            Archive
          </Button>
          <Popconfirm
            title="确认删除此分支？"
            okText="删除"
            cancelText="取消"
            onConfirm={() => handleDelete(r)}
          >
            <Button size="small" type="link" danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div data-testid="branch-list" style={{ padding: 16 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} wrap>
        <Title level={3} style={{ margin: 0 }}>{t('ontology.branch.title') || '本体分支管理'}</Title>
        <Space>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="搜索分支..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 240 }}
          />
          <Button icon={<ReloadOutlined />} onClick={() => void fetchBranches()}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateOpen(true)}
          >
            New Branch
          </Button>
        </Space>
      </Space>

      <Card>
        <Spin spinning={loading}>
          {filtered.length === 0 ? (
            <Empty description="暂无分支" />
          ) : (
            <AdvancedTable<BranchInfo>
              rowKey="branch_id"
              size="small"
              dataSource={filtered}
              columns={columns}
              pagination={{ pageSize: 10 }}
            />
          )}
        </Spin>
      </Card>

      <Modal
        title="创建分支"
        open={createOpen}
        onOk={handleCreate}
        onCancel={() => { setCreateOpen(false); form.resetFields(); }}
        confirmLoading={creating}
        okText="创建"
        cancelText="取消"
        destroyOnHidden
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item
            name="name"
            label="分支名"
            rules={[
              { required: true, message: '请输入分支名' },
              { pattern: /^[a-zA-Z0-9_/][a-zA-Z0-9_/-]*$/, message: '分支名仅允许字母、数字、下划线、连字符和斜杠' },
            ]}
          >
            <Input placeholder="feature/new-ontology" />
          </Form.Item>
          <Form.Item name="base_version_id" label="基于版本">
            <Select
              allowClear
              placeholder="选择基础版本"
              options={versionOptions}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={3} placeholder="本次分支的目的和范围" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default BranchList;
