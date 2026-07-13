/**
 * 规范术语 (UslTerm) 表格
 * 列：canonical(Tag 显示 semantic_type 颜色) / en / 同义词 Chips / 近义词 / 别名 /
 *     Stoplist Switch（onChange 直接调用 updateTerm）/ 操作
 */
import React, { useEffect, useState, useMemo } from 'react';
import {
  Table,
  Button,
  Space,
  Input,
  Tag,
  App,
  Tooltip,
  Switch,
  Select,
  Typography,
  Chips,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined,
  EditOutlined,
  SearchOutlined,
  ReloadOutlined,
  DeleteOutlined,
  ExclamationCircleFilled,
} from '@ant-design/icons';
import {
  SEMANTIC_TYPE_LABEL,
  SEMANTIC_TYPE_COLOR,
  type UslTerm,
  type SemanticType,
} from '../types';
import { listTerms, updateTerm } from '../services/uslApi';
import { useSemanticAdminStore } from '../store/useSemanticAdminStore';
import { useUslPermissions } from '../hooks/useUslPermissions';
import { TermForm, type TermFormValues } from './TermForm';

const { Text } = Typography;

export function TermTable() {
  const { message, modal } = App.useApp();
  const { canWrite } = useUslPermissions();
  const currentDomain = useSemanticAdminStore((s) => s.currentDomain);
  const filters = useSemanticAdminStore((s) => s.filters);
  const termPage = useSemanticAdminStore((s) => s.termPage);
  const termPageSize = useSemanticAdminStore((s) => s.termPageSize);
  const setTermPage = useSemanticAdminStore((s) => s.setTermPage);
  const setTermPageSize = useSemanticAdminStore((s) => s.setTermPageSize);
  const setTermSemanticType = useSemanticAdminStore((s) => s.setTermSemanticType);
  const setTermKeyword = useSemanticAdminStore((s) => s.setTermKeyword);
  const setTermStoplist = useSemanticAdminStore((s) => s.setTermStoplist);

  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<UslTerm[]>([]);
  const [total, setTotal] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<UslTerm | null>(null);

  const fetchData = async () => {
    if (!currentDomain) return;
    setLoading(true);
    try {
      const res = await listTerms(currentDomain.code, {
        page: termPage,
        page_size: termPageSize,
        semantic_type: filters.termSemanticType || undefined,
        synonym_keyword: filters.termKeyword || undefined,
      });
      // 前端本地过滤 stoplist：后端 list_terms 未开放 stoplist 查询参数
      const needStoplistFilter = filters.termStoplist !== null
        && filters.termStoplist !== undefined
        && filters.termStoplist !== '';
      const list = res.items || [];
      const filtered = needStoplistFilter
        ? list.filter((t) => Boolean(t.stoplist_flag) === Boolean(filters.termStoplist))
        : list;
      setItems(filtered);
      setTotal(needStoplistFilter ? filtered.length : (res.total || 0));
    } catch (err) {
      console.warn('[TermTable] listTerms failed:', err);
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
  }, [
    currentDomain?.code,
    termPage,
    termPageSize,
    filters.termSemanticType,
    filters.termKeyword,
    filters.termStoplist,
  ]);

  const handleToggleStoplist = async (record: UslTerm, checked: boolean) => {
    if (!record.id) return;
    try {
      await updateTerm(record.id, { stoplist: checked });
      message.success(`术语「${record.canonical}」已${checked ? '加入' : '移出'}停用词表`);
      void fetchData();
    } catch (err) {
      message.error(`切换失败：${err instanceof Error ? err.message : String(err)}`);
      void fetchData(); // 回滚 UI
    }
  };

  const handleDelete = (record: UslTerm) => {
    modal.confirm({
      title: `删除术语「${record.canonical}」？`,
      icon: <ExclamationCircleFilled />,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      content: '删除后同义词/近义词/别名等信息都将丢失；停用建议用 Stoplist 开关',
      onOk: () => {
        // 复用更新模式：后端未暴露 delete term，提示待上线
        message.info('删除术语接口待上线；当前可使用 Stoplist 停用');
      },
    });
  };

  const semanticTypeOptions = useMemo(() => {
    const entries = Object.entries(SEMANTIC_TYPE_LABEL) as Array<[SemanticType, string]>;
    return [
      { label: '全部', value: '' },
      ...entries.map(([k, v]) => ({ label: v, value: k })),
    ];
  }, []);

  const columns: ColumnsType<UslTerm> = [
    {
      title: '规范词 canonical',
      dataIndex: 'canonical',
      width: 160,
      fixed: 'left',
      render: (v: string, r) => (
        <Space size="small">
          <Text strong>{v}</Text>
          <Tag color={SEMANTIC_TYPE_COLOR[r.semantic_type]}>
            {SEMANTIC_TYPE_LABEL[r.semantic_type]}
          </Tag>
        </Space>
      ),
    },
    {
      title: '英文 en',
      dataIndex: 'en',
      width: 160,
      render: (v?: string) => v ? <Text code>{v}</Text> : <Text type="secondary">—</Text>,
    },
    {
      title: '同义词',
      dataIndex: 'synonyms',
      width: 200,
      render: (arr?: string[]) =>
        arr && arr.length ? (
          <Chips options={arr.map((x) => ({ label: x, value: x }))} size="small" closable={false} />
        ) : (
          <Text type="secondary">空</Text>
        ),
    },
    {
      title: '近义词',
      dataIndex: 'near_synonyms',
      width: 180,
      render: (arr?: string[]) =>
        arr && arr.length ? (
          <Text ellipsis style={{ maxWidth: 180 }}>{arr.join('、')}</Text>
        ) : (
          <Text type="secondary">空</Text>
        ),
    },
    {
      title: '别名',
      dataIndex: 'aliases',
      width: 180,
      render: (arr?: string[]) =>
        arr && arr.length ? (
          <Text ellipsis style={{ maxWidth: 180 }}>{arr.join(' / ')}</Text>
        ) : (
          <Text type="secondary">空</Text>
        ),
    },
    {
      title: '停用词',
      dataIndex: 'stoplist',
      width: 110,
      align: 'center',
      render: (v: boolean | undefined, record) => (
        <Tooltip title={canWrite ? '点击切换停用' : '无写权限'}>
          <Switch
            size="small"
            checked={!!v}
            disabled={!canWrite || !record.id}
            onChange={(checked) => handleToggleStoplist(record, checked)}
          />
        </Tooltip>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      fixed: 'right',
      render: (_: unknown, record) => (
        <Space size="small">
          <Tooltip title={canWrite ? '' : '需要 admin / schema_auditor'}>
            <Button
              size="small"
              type="text"
              icon={<EditOutlined />}
              disabled={!canWrite}
              onClick={() => {
                setEditing(record);
                setFormOpen(true);
              }}
            >
              编辑
            </Button>
          </Tooltip>
          <Tooltip title={canWrite ? '建议用 Stoplist 代替删除' : ''}>
            <Button
              size="small"
              danger
              type="text"
              icon={<DeleteOutlined />}
              disabled={!canWrite}
              onClick={() => handleDelete(record)}
            >
              删除
            </Button>
          </Tooltip>
        </Space>
      ),
    },
  ];

  if (!currentDomain) {
    return (
      <App>
        <div
          style={{
            padding: 48,
            textAlign: 'center',
            color: '#8c8c8c',
            background: '#fafafa',
            borderRadius: 6,
          }}
        >
          请先在「语义域列表」Tab 中选择一个语义域，然后再查阅术语。
        </div>
      </App>
    );
  }

  return (
    <App>
      <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }} wrap>
        <Space wrap>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="搜索 canonical / en / 同义词"
            value={filters.termKeyword}
            onChange={(e) => setTermKeyword(e.target.value)}
            onPressEnter={() => setTermPage(1)}
            style={{ width: 280 }}
          />
          <Select
            style={{ width: 160 }}
            value={filters.termSemanticType || ''}
            onChange={(v) => setTermSemanticType(v)}
            options={semanticTypeOptions}
          />
          <Select
            style={{ width: 140 }}
            value={
              filters.termStoplist === null
                ? 'all'
                : filters.termStoplist
                  ? 'only_stop'
                  : 'only_active'
            }
            onChange={(v: string) =>
              setTermStoplist(v === 'all' ? null : v === 'only_stop' ? true : false)
            }
            options={[
              { label: '全部（含停用）', value: 'all' },
              { label: '仅启用中', value: 'only_active' },
              { label: '仅停用', value: 'only_stop' },
            ]}
          />
          <Button icon={<ReloadOutlined />} onClick={() => void fetchData()}>
            刷新
          </Button>
        </Space>
        <Tooltip title={canWrite ? '' : '需要 admin / schema_auditor'}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            disabled={!canWrite}
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            新建术语
          </Button>
        </Tooltip>
      </Space>

      <Table<UslTerm>
        rowKey={(r) => r.id || `${r.canonical}-${r.semantic_type}`}
        size="middle"
        loading={loading}
        columns={columns}
        dataSource={items}
        scroll={{ x: 1200 }}
        pagination={{
          current: termPage,
          pageSize: termPageSize,
          total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => {
            setTermPage(p);
            setTermPageSize(ps);
          },
        }}
      />

      <TermForm
        open={formOpen}
        mode={editing ? 'edit' : 'create'}
        initial={editing || undefined}
        onCancel={() => setFormOpen(false)}
        onSubmitted={() => {
          setFormOpen(false);
          void fetchData();
        }}
      />
    </App>
  );
}

export type { TermFormValues };
