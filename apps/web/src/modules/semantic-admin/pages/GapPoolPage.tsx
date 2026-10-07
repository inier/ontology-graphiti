import React, { useCallback, useEffect, useState } from 'react';
import { Table, Tag, Button, Space, Select, Modal, Input, message } from 'antd';
import { gapApi, type GapItem } from '../services/gapApi';

const STATUS_COLOR: Record<string, string> = {
  open: 'orange', promoted: 'blue', adopted: 'green', rejected: 'default',
};

export const GapPoolPage: React.FC = () => {
  const [items, setItems] = useState<GapItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | undefined>();
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await gapApi.list({ status, page, page_size: 20 });
      setItems(r.items ?? []);
      setTotal(r.total ?? 0);
    } catch (e) {
      message.error((e as Error).message || '加载缺口池失败');
    } finally {
      setLoading(false);
    }
  }, [status, page]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, [load]);

  const onPromote = async (id: string) => {
    try { await gapApi.promote(id); message.success('已晋升为候选'); load(); }
    catch (e) { message.error((e as Error).message || '晋升失败'); }
  };
  const onDismiss = (id: string) => {
    let reason = '';
    Modal.confirm({
      title: '忽略该缺口', content: <Input.TextArea onChange={(e) => (reason = e.target.value)} />,
      onOk: async () => {
        try { await gapApi.dismiss(id, reason); message.success('已忽略'); load(); }
        catch (e) { message.error((e as Error).message || '忽略失败'); }
      },
    });
  };
  const onResolveCheck = async (id: string) => {
    try {
      const r = await gapApi.resolveCheck(id);
      Modal.info({ title: 'resolve-check', content: `${r.via}: ${r.detail}` });
    } catch (e) { message.error((e as Error).message || 'resolve-check 失败'); }
  };

  const columns = [
    { title: '说法', dataIndex: 'expression', key: 'expression' },
    { title: '热度', dataIndex: 'heat', key: 'heat', sorter: (a: GapItem, b: GapItem) => a.heat - b.heat },
    { title: '来源', key: 'sources', render: (_: unknown, r: GapItem) =>
        Object.entries(r.source_counts_json || {}).map(([k, v]) => <Tag key={k}>{k}:{v}</Tag>) },
    { title: '状态', dataIndex: 'status', key: 'status',
      render: (s: string) => <Tag color={STATUS_COLOR[s]}>{s}</Tag> },
    { title: '最近', dataIndex: 'last_seen', key: 'last_seen' },
    { title: '操作', key: 'op', render: (_: unknown, r: GapItem) => (
        <Space>
          {r.status === 'open' && <Button size="small" onClick={() => onPromote(r.id)}>晋升</Button>}
          {r.status === 'open' && <Button size="small" danger onClick={() => onDismiss(r.id)}>忽略</Button>}
          <Button size="small" onClick={() => onResolveCheck(r.id)}>resolve-check</Button>
        </Space>) },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Space style={{ marginBottom: 12 }}>
        <Select allowClear placeholder="状态过滤" style={{ width: 160 }} value={status}
          onChange={(v) => { setStatus(v); setPage(1); }}
          options={['open', 'promoted', 'adopted', 'rejected'].map((s) => ({ label: s, value: s }))} />
        <Button onClick={load}>刷新</Button>
      </Space>
      <Table rowKey="id" loading={loading} columns={columns} dataSource={items}
        pagination={{ current: page, total, pageSize: 20,
          onChange: (p) => setPage(p) }} />
    </div>
  );
};

export default GapPoolPage;
