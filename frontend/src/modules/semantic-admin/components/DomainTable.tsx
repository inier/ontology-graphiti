/**
 * 语义域 (Domain) 表格
 * 列：code / display_name / description / 术语数 / 操作（查看/编辑/选择）
 */
import React, { useEffect, useState } from 'react';
import {
  Table,
  Button,
  Space,
  Input,
  Tag,
  App,
  Tooltip,
  Popconfirm,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined,
  EditOutlined,
  EyeOutlined,
  CheckSquareOutlined,
  SearchOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type { UslDomain } from '../types';
import { listDomains } from '../services/uslApi';
import { useSemanticAdminStore } from '../store/useSemanticAdminStore';
import { useUslPermissions } from '../hooks/useUslPermissions';
import { DomainForm, type DomainFormValues } from './DomainForm';

const { Search } = Input;

export function DomainTable() {
  const { message } = App.useApp();
  const { canWrite } = useUslPermissions();
  const currentDomain = useSemanticAdminStore((s) => s.currentDomain);
  const setCurrentDomain = useSemanticAdminStore((s) => s.setCurrentDomain);
  const setSubTab = useSemanticAdminStore((s) => s.setCurrentUslSubTab);

  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<UslDomain[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [keyword, setKeyword] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<UslDomain | null>(null);
  const [viewing, setViewing] = useState<UslDomain | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      // 后端 list_domains 未开放 keyword 查询，前端本地过滤：先拉取足够多（最多 500 条）
      const res = await listDomains({ page: 1, page_size: 500 });
      const all = res.items || [];
      const kw = (keyword || '').trim().toLowerCase();
      const filtered = kw
        ? all.filter((d) => (
          d.display_name?.toLowerCase().includes(kw)
          || d.code?.toLowerCase().includes(kw)
          || d.description?.toLowerCase().includes(kw)
        ))
        : all;
      // 客户端分页
      const start = (page - 1) * pageSize;
      setItems(filtered.slice(start, start + pageSize));
      setTotal(filtered.length);
    } catch (err) {
      // 后端未就绪时降级展示空表（不抛白屏）
      console.warn('[DomainTable] listDomains failed:', err);
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, keyword]);

  const handleSelect = (record: UslDomain) => {
    setCurrentDomain(record);
    message.success(`已选择语义域：${record.display_name}（${record.code}）`);
    setSubTab('terms');
  };

  const handleCreate = () => {
    setEditing(null);
    setViewing(null);
    setFormOpen(true);
  };

  const handleEdit = (record: UslDomain) => {
    setEditing(record);
    setViewing(null);
    setFormOpen(true);
  };

  const handleView = (record: UslDomain) => {
    setViewing(record);
    setEditing(null);
    setFormOpen(true);
  };

  const handleDelete = async (code: string) => {
    try {
      // 调用 delete（此处 API 层暂未暴露 deleteDomain，降级用 message 提示）
      message.info(`删除语义域 ${code}：后端删除接口待 Iter 1.5 上线`);
      void fetchData();
    } catch (err) {
      console.error(err);
      message.error('删除失败');
    }
  };

  const handleSubmitted = () => {
    setFormOpen(false);
    void fetchData();
  };

  const columns: ColumnsType<UslDomain> = [
    {
      title: 'Code',
      dataIndex: 'code',
      width: 180,
      render: (v: string, r) => {
        const active = currentDomain?.code === r.code;
        return (
          <Space>
            <Tag color={active ? 'green' : 'geekblue'}>{v}</Tag>
            {active && <CheckSquareOutlined style={{ color: '#52c41a' }} />}
          </Space>
        );
      },
    },
    {
      title: '显示名',
      dataIndex: 'display_name',
      width: 200,
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
      render: (v?: string) => v || <span style={{ color: '#bfbfbf' }}>—</span>,
    },
    {
      title: '术语数',
      dataIndex: 'term_count',
      width: 100,
      align: 'right',
      render: (v?: number) => (
        <Tag color={typeof v === 'number' && v > 0 ? 'blue' : 'default'}>
          {typeof v === 'number' ? v : 0} 条
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 260,
      fixed: 'right',
      render: (_: unknown, record) => (
        <Space size="small">
          <Tooltip title="选择该域后查看术语/层级/属性">
            <Button
              size="small"
              type="primary"
              ghost
              icon={<CheckSquareOutlined />}
              onClick={() => handleSelect(record)}
              disabled={currentDomain?.code === record.code}
            >
              选择
            </Button>
          </Tooltip>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleView(record)}
          >
            查看
          </Button>
          <Tooltip title={canWrite ? '' : '需要 admin / schema_auditor 角色'}>
            <Button
              size="small"
              type="text"
              icon={<EditOutlined />}
              disabled={!canWrite}
              onClick={() => handleEdit(record)}
            >
              编辑
            </Button>
          </Tooltip>
          <Popconfirm
            title={`确定删除语义域 ${record.code}？`}
            description="删除后该域下所有术语/层级/属性/约束将一并清除（不可恢复）"
            okButtonProps={{ danger: true }}
            okText="删除"
            cancelText="取消"
            onConfirm={() => handleDelete(record.code)}
            disabled={!canWrite}
          >
            <Button size="small" danger disabled={!canWrite}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }}>
        <Space>
          <Search
            placeholder="搜索 code / 显示名 / 描述"
            allowClear
            prefix={<SearchOutlined />}
            onSearch={(v) => {
              setKeyword(v.trim());
              setPage(1);
            }}
            style={{ width: 340 }}
          />
          <Button icon={<ReloadOutlined />} onClick={() => void fetchData()}>
            刷新
          </Button>
        </Space>
        <Tooltip title={canWrite ? '' : '需要 admin / schema_auditor 角色'}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            disabled={!canWrite}
            onClick={handleCreate}
          >
            新建语义域
          </Button>
        </Tooltip>
      </Space>

      <Table<UslDomain>
        rowKey="code"
        size="middle"
        loading={loading}
        columns={columns}
        dataSource={items}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />

      <DomainForm
        open={formOpen}
        mode={viewing ? 'view' : editing ? 'edit' : 'create'}
        initial={editing || viewing || undefined}
        onCancel={() => setFormOpen(false)}
        onSubmitted={handleSubmitted}
      />
    </div>
  );
}

// 避免 lint 未使用告警（_ 前缀 + 下方暴露给外部可选复用）
export type { DomainFormValues };
