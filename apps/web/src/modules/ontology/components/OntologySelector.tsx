import { useState, useEffect, useCallback } from 'react';
import { Modal, Button, Input, Form, Tag, Space, message } from 'antd';
import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';
import { AdvancedTable } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface OntologyItem {
  ontology_id: string;
  name: string;
  description: string;
  workspace_id: string;
  scenario_id: string | null;
  current_version: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface OntologySelectorProps {
  open: boolean;
  onClose: () => void;
  onSelect: (ontology: OntologyItem) => void;
  workspaceId?: string;
  /** 直接进入新建流程，跳过列表 */
  initialCreate?: boolean;
}

/* ------------------------------------------------------------------ */
/*  API helpers                                                        */
/* ------------------------------------------------------------------ */

async function listOntologies(workspaceId?: string): Promise<{ ontologies: OntologyItem[]; count: number }> {
  const params = new URLSearchParams();
  if (workspaceId) params.set('workspace_id', workspaceId);
  const qs = params.toString();
  return fetchJson(`${API_BASE}/api/ontologies${qs ? '?' + qs : ''}`);
}

async function createOntology(data: {
  name: string;
  description?: string;
  workspace_id?: string;
  scenario_id?: string;
}): Promise<OntologyItem> {
  return fetchJson(`${API_BASE}/api/ontologies`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/* ------------------------------------------------------------------ */
/*  Status color mapping                                               */
/* ------------------------------------------------------------------ */

const STATUS_COLORS: Record<string, string> = {
  draft: 'default',
  active: 'green',
  archived: 'orange',
  deprecated: 'red',
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function OntologySelector({ open, onClose, onSelect, workspaceId, initialCreate }: OntologySelectorProps) {
  const { t } = useI18n('ontology');
  const [ontologies, setOntologies] = useState<OntologyItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm] = Form.useForm();
  const [creating, setCreating] = useState(false);

  // ---- Load ontologies ----
  const loadOntologies = useCallback(async () => {
    setLoading(true);
    try {
      const result = await listOntologies(workspaceId);
      setOntologies(result.ontologies || []);
    } catch (e) {
      console.error('Failed to load ontologies:', e);
      setOntologies([]);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    if (open) {
      loadOntologies();
      setShowCreateForm(!!initialCreate);
    }
  }, [open, loadOntologies, initialCreate]);

  // ---- Create ontology ----
  const handleCreate = useCallback(async () => {
    try {
      const values = await createForm.validateFields();
      setCreating(true);
      const newOntology = await createOntology({
        name: values.name,
        description: values.description || '',
        workspace_id: values.workspace_id || workspaceId || '',
      });
      message.success(t('本体创建成功'));
      setShowCreateForm(false);
      createForm.resetFields();
      // Refresh list then auto-select
      await loadOntologies();
      if (newOntology) {
        onSelect(newOntology);
      }
    } catch (e: unknown) {
      // Form validation errors are handled by antd; API errors shown here
      if (e && typeof e === 'object' && 'errorFields' in e) return;
      console.error('Failed to create ontology:', e);
      message.error(t('创建本体失败'));
    } finally {
      setCreating(false);
    }
  }, [createForm, workspaceId, loadOntologies, onSelect]);

  // ---- Row click ----
  const handleRowClick = useCallback(
    (record: OntologyItem) => {
      onSelect(record);
    },
    [onSelect],
  );

  // ---- Filtered data ----
  const filteredData = searchText
    ? ontologies.filter(
        (o) =>
          o.name.toLowerCase().includes(searchText.toLowerCase()) ||
          o.description.toLowerCase().includes(searchText.toLowerCase()),
      )
    : ontologies;

  // ---- Table columns ----
  const columns = [
    {
      title: t('名称'),
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: t('描述'),
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (text: string) => text || '-',
    },
    {
      title: t('状态'),
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => (
        <Tag color={STATUS_COLORS[status] || 'default'}>{status || 'draft'}</Tag>
      ),
    },
    {
      title: t('当前版本'),
      dataIndex: 'current_version',
      key: 'current_version',
      width: 110,
      render: (v: string) => v || '-',
    },
    {
      title: t('创建时间'),
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => (v ? new Date(v).toLocaleString() : '-'),
    },
    {
      title: t('操作'),
      key: 'action',
      width: 80,
      render: (_: unknown, record: OntologyItem) => (
        <Button type="primary" size="small" onClick={(e) => { e.stopPropagation(); handleRowClick(record); }}>
          {t('选择')}
        </Button>
      ),
    },
  ];

  return (
    <Modal
      title={t('选择本体')}
      open={open}
      onCancel={onClose}
      footer={null}
      width={800}
      destroyOnHidden
    >
      {/* Toolbar */}
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Input
          prefix={<SearchOutlined />}
          placeholder={t('搜索本体...')}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
          style={{ width: 260 }}
        />
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setShowCreateForm((prev) => !prev);
            if (!showCreateForm) {
              createForm.resetFields();
            }
          }}
        >
          {showCreateForm ? t('取消新建') : t('新建本体')}
        </Button>
      </Space>

      {/* Inline create form */}
      {showCreateForm && (
        <div
          style={{
            marginBottom: 16,
            padding: 16,
            border: '1px solid #d9d9d9',
            borderRadius: 8,
            background: '#fafafa',
          }}
        >
          <Form form={createForm} layout="inline" style={{ gap: 12, flexWrap: 'wrap' }}>
            <Form.Item
              name="name"
              rules={[{ required: true, message: t('请输入本体名称') }]}
              style={{ marginBottom: 8 }}
            >
              <Input placeholder={t('本体名称（必填）')} style={{ width: 180 }} />
            </Form.Item>
            <Form.Item name="description" style={{ marginBottom: 8 }}>
              <Input placeholder={t('描述')} style={{ width: 200 }} />
            </Form.Item>
            {!workspaceId && (
              <Form.Item name="workspace_id" style={{ marginBottom: 8 }}>
                <Input placeholder={t('工作空间 ID')} style={{ width: 160 }} />
              </Form.Item>
            )}
            <Form.Item style={{ marginBottom: 8 }}>
              <Button type="primary" onClick={handleCreate} loading={creating}>
                {t('创建')}
              </Button>
            </Form.Item>
          </Form>
        </div>
      )}

      {/* Ontology table */}
      <AdvancedTable
        rowKey="ontology_id"
        columns={columns}
        dataSource={filteredData}
        loading={loading}
        size="middle"
        pagination={{ pageSize: 8, showSizeChanger: false }}
        onRow={(record) => ({
          onClick: () => handleRowClick(record),
          style: { cursor: 'pointer' },
        })}
        locale={{ emptyText: t('暂无本体数据') }}
      />
    </Modal>
  );
}

export default OntologySelector;
