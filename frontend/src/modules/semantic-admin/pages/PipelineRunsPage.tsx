import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Row, Col, Input, Select, Button, Space, Table,
  Tag, Progress, Tooltip, Drawer, Typography, Tabs, Badge,
  Steps, Tree, Empty, Alert, Divider, Statistic, Card,
} from 'antd';
import type { TableProps, TreeDataNode } from 'antd';
import { ReloadOutlined, ClearOutlined, PlayCircleOutlined, EyeOutlined, CopyOutlined, BulbOutlined, BranchesOutlined, NodeIndexOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { SEMANTIC_ADMIN_TAB_ITEMS, TOP_TAB_TO_PATH } from '../constants';
import { useSemanticAdminStore } from '../store/useSemanticAdminStore';
import type { CandidateFilters, PipelineRunFilters } from '../store/useSemanticAdminStore';
import type { PipelineRun, PipelineRunStatus } from '../services/pipelineApi';
import { getPipelineRuns, runPipelineNow } from '../services/pipelineApi';

const ST_OPS: Array<{ label: string; value: PipelineRunStatus }> = [
  { label: 'pending', value: 'pending' }, { label: 'running', value: 'running' },
  { label: 'succeeded', value: 'succeeded' }, { label: 'failed', value: 'failed' },
];
const ST_COL: Record<string, string> = { running: 'blue', pending: 'default', succeeded: 'green', failed: 'red' };
const GD_COL: Record<string, string> = { A: '#52c41a', B: '#1677ff', C: '#faad14', D: '#ff4d4f' };
const LAYER_KEYS = ['L1_tokens', 'L2_concepts', 'L3_entities', 'L4_relations', 'L5_patterns', 'L6_axioms'] as const;

const sId = (id?: string, n = 8): string => !id ? '-' : id.length > n * 2 + 3 ? `${id.slice(0, n)}...${id.slice(-4)}` : id;
const fmt = (s?: string): string => !s ? '-' : s.substring(0, 19).replace('T', ' ');
const copy = (v: string) => { try { navigator.clipboard.writeText(v); message.success('Copied'); } catch { message.error('Copy failed'); } };

const LAYER_LABELS: Record<string, { title: string; desc: string; icon: React.ReactNode }> = {
  L1_tokens: { title: 'L1 Tokens 归一', desc: '同义词合并 / 规范校正 / 词频过滤', icon: <BulbOutlined /> },
  L2_concepts: { title: 'L2 Concepts 上下位', desc: '上下位抽取 / 传递闭包 / 环检测', icon: <BranchesOutlined /> },
  L3_entities: { title: 'L3 FCA 形式概念', desc: '概念格 Hasse 图 / stability ≥ 0.6 输出', icon: <NodeIndexOutlined /> },
  L4_relations: { title: 'L4 Relations 关系', desc: 'is-a / part-of / attribute-of / related-to 发现', icon: <BranchesOutlined /> },
  L5_patterns: { title: 'L5 Fusion 融合', desc: 'merge / keep-as-new / flag-conflict 三分类', icon: <NodeIndexOutlined /> },
  L6_axioms: { title: 'L6 Axioms 公理', desc: 'subClassOf / disjoint / domain / range / cardinality', icon: <BulbOutlined /> },
};

const layerIndexOf = (k: string) => Object.keys(LAYER_LABELS).indexOf(k);

function deriveCurrentLayer(run?: PipelineRun): number {
  if (!run) return 0;
  const st = run.status;
  if (st === 'pending') return 0;
  if (st === 'running') return (run.progress ? Math.min(5, Math.floor(run.progress * 6)) : 1);
  if (st === 'failed') return Math.max(0, Math.min(5, Math.floor((run.progress || 0.3) * 6) - 1));
  if (st === 'succeeded' || st === 'COMPLETED') return 6;
  // l1_done..l6_done
  const m = /^l(\d)_done$/.exec(st || '');
  if (m) return Math.min(6, parseInt(m[1], 10));
  return 0;
}

const MOCK_L3_HASSE_TREE: TreeDataNode[] = [
  {
    title: '⊤ 顶概念 (全部样本)',
    key: 'c-top',
    children: [
      {
        title: '商品类 Product (extent=58)',
        key: 'c-product',
        children: [
          { title: '数码产品 Digital (extent=22)', key: 'c-digital', children: [
            { title: '手机 Phone (extent=9)', key: 'c-phone' },
            { title: '笔记本 Laptop (extent=7)', key: 'c-laptop' },
            { title: '耳机 Earphone (extent=6)', key: 'c-earphone' },
          ]},
          { title: '服饰 Apparel (extent=19)', key: 'c-apparel', children: [
            { title: '男装 Men (extent=8)', key: 'c-men' },
            { title: '女装 Women (extent=11)', key: 'c-women' },
          ]},
          { title: '食品 Food (extent=17)', key: 'c-food' },
        ],
      },
      {
        title: '品牌 Brand (extent=36)',
        key: 'c-brand',
      },
      {
        title: '订单 Order (extent=41)',
        key: 'c-order',
      },
    ],
  },
];

type RelBubble = { name: string; x: number; y: number; r: number; kind: 'is-a' | 'part-of' | 'attribute-of' | 'related-to'; };
const REL_KIND_COLOR: Record<RelBubble['kind'], string> = {
  'is-a': '#1677ff',
  'part-of': '#52c41a',
  'attribute-of': '#722ed1',
  'related-to': '#fa8c16',
};
const MOCK_L4_BUBBLES: RelBubble[] = (() => {
  const names = ['Product', 'Digital', 'Phone', 'Laptop', 'Screen', 'CPU', 'Memory', 'Camera',
    'Apparel', 'Men', 'Women', 'Shirt', 'Shoe', 'Size', 'Color', 'Brand', 'Order', 'Customer',
    'Food', 'Snack', 'Beverage', 'Expiry', 'Price', 'SKU', 'Stock', 'Category', 'SubCategory',
    'Attribute', 'Property', 'Weight', 'Material', 'Origin', 'Warranty', 'Discount', 'Rating',
    'Review', 'Shipment', 'Invoice', 'Tax', 'Specification', 'Model', 'Manufacturer', 'Supplier',
    'Season', 'Style', 'Packaging', 'Label', 'Barcode', 'Storage'];
  const kinds: RelBubble['kind'][] = ['is-a', 'part-of', 'attribute-of', 'related-to'];
  const arr: RelBubble[] = [];
  for (let i = 0; i < 50; i++) {
    const angle = (i / 50) * Math.PI * 2;
    const radius = 40 + ((i * 37) % 110);
    arr.push({
      name: names[i % names.length] + (i >= names.length ? String(Math.floor(i / names.length)) : ''),
      x: 200 + Math.cos(angle) * radius,
      y: 180 + Math.sin(angle) * radius,
      r: 8 + ((i * 13) % 18),
      kind: kinds[i % 4],
    });
  }
  return arr;
})();

const PipelineRunsPage: React.FC = () => {
  const nav = useNavigate();
  const prf = useSemanticAdminStore((s) => s.pipelineRunFilters);
  const setPRF = useSemanticAdminStore((s) => s.setPipelineRunFilters);
  const resetPRF = useSemanticAdminStore((s) => s.resetPipelineRunFilters);
  const setCF = useSemanticAdminStore((s) => s.setCandidateFilters);
  const [data, setData] = useState<PipelineRun[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [dr, setDr] = useState<{ open: boolean; run?: PipelineRun }>({ open: false });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const r = await getPipelineRuns({
        workspace_id: prf.workspace_id, status: (prf.status as PipelineRunStatus) || undefined,
        page: prf.page, page_size: prf.page_size,
      });
      setData(r.items || []); setTotal(r.total ?? 0);
    } catch (e) { message.error((e as Error).message || 'Failed to load'); setData([]); setTotal(0); }
    finally { setLoading(false); }
  }, [prf]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { fetchData(); }, [fetchData]);
  const onF = (p: Partial<PipelineRunFilters>) => setPRF({ ...p, page: 1 });
  const onRerun = async (r: PipelineRun) => { try { await runPipelineNow(r.id); message.success(`Run triggered: ${sId(r.id)}`); fetchData(); } catch (e) { message.error((e as Error).message || 'Rerun failed'); } };
  const jump = (runId: string) => { const patch: Partial<CandidateFilters> = { pipeline_run_id: runId, page: 1 }; setCF(patch); nav('/semantic-admin/candidates'); };

  const cols: TableProps<PipelineRun>['columns'] = [
    { title: 'Run ID', dataIndex: 'id', key: 'id', width: 200, render: (v: string) => <Space><Tooltip title={v}><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{sId(v, 6)}</span></Tooltip><Button type="text" size="small" icon={<CopyOutlined />} onClick={() => copy(v)} /></Space> },
    { title: 'Workspace', dataIndex: 'workspace_id', key: 'ws', width: 130, render: (v: string) => <Tooltip title={v}><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{sId(v, 6)}</span></Tooltip> },
    { title: 'Source', dataIndex: 'source_type', key: 'src', width: 110, render: (v: string, r) => <Tooltip title={r.source_ref}><Tag color="geekblue">{v}</Tag></Tooltip> },
    { title: 'Status', dataIndex: 'status', key: 'st', width: 100, render: (v: string) => <Tag color={ST_COL[v] ?? 'default'}>{v}</Tag> },
    { title: 'Progress', dataIndex: 'progress', key: 'pg', width: 160, render: (v: number) => <Progress percent={Math.round(v * 100)} size="small" /> },
    { title: 'Layers', key: 'L', width: 180, render: (_, r) => r.stats ? <Space size={4} wrap>{LAYER_KEYS.map((k) => { const stats = r.stats as Record<string, number>; const n = stats[k]; if (n == null) return null; return <Badge key={k} count={`${k.split('_')[0]}:${n}`} style={{ backgroundColor: '#f0f5ff', color: '#1677ff', boxShadow: 'none', border: '1px solid #d6e4ff' }} />; })}</Space> : '-' },
    { title: 'Input', dataIndex: 'total_input_chars', key: 'ic', width: 90, align: 'right', render: (v: number) => v?.toLocaleString() ?? '0' },
    { title: 'Candidates', dataIndex: 'total_output_candidates', key: 'oc', width: 110, align: 'right', render: (v: number, r) => <a onClick={() => jump(r.id)} style={{ cursor: 'pointer' }}>{v?.toLocaleString() ?? 0}</a> },
    { title: 'Grades', key: 'G', width: 140, render: (_, r) => { const g = r.stats?.grades; if (!g) return '-'; const grades = g as Record<string, number>; const tot = (grades.A ?? 0) + (grades.B ?? 0) + (grades.C ?? 0) + (grades.D ?? 0); if (!tot) return '-'; return <div style={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden' }}>{(['A','B','C','D'] as const).map((k) => { const n = grades[k] ?? 0; const p = tot ? (n / tot) * 100 : 0; return p > 0 ? <div key={k} style={{ width: `${p}%`, backgroundColor: GD_COL[k] }} /> : null; })}</div>; } },
    { title: 'Started', dataIndex: 'started_at', key: 'sa', width: 150, render: (v?: string) => fmt(v) },
    { title: 'Finished', dataIndex: 'finished_at', key: 'fa', width: 150, render: (v?: string) => fmt(v) },
    { title: 'Actions', key: 'act', width: 150, fixed: 'right', render: (_, r) => <Space><Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => onRerun(r)}>Rerun</Button><Button type="link" size="small" icon={<EyeOutlined />} onClick={() => setDr({ open: true, run: r })}>Details</Button></Space> },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Tabs activeKey="pipeline" onChange={(k) => { const p = TOP_TAB_TO_PATH[k as keyof typeof TOP_TAB_TO_PATH]; if (p) { nav(p); } }} items={SEMANTIC_ADMIN_TAB_ITEMS} style={{ marginBottom: 8 }} />
      <Row gutter={[12, 12]} align="middle" style={{ marginBottom: 12 }}>
        <Col span={6}><Input allowClear placeholder="Workspace ID" value={prf.workspace_id} onChange={(e) => onF({ workspace_id: e.target.value })} /></Col>
        <Col span={4}><Select allowClear style={{ width: '100%' }} placeholder="Status" value={prf.status || undefined} onChange={(v) => onF({ status: v ?? '' })} options={ST_OPS} /></Col>
        <Col span={14} style={{ textAlign: 'right' }}><Space>
          <Button icon={<ClearOutlined />} onClick={() => { resetPRF(); fetchData(); }}>Reset</Button>
          <Button type="primary" icon={<ReloadOutlined />} onClick={() => fetchData()}>Refresh</Button>
        </Space></Col>
      </Row>
      <Table<PipelineRun> rowKey="id" loading={loading} dataSource={data} columns={cols}
        pagination={{ current: prf.page, pageSize: prf.page_size, total, showSizeChanger: true, showQuickJumper: true, showTotal: (t) => `Total ${t} runs`, onChange: (page, page_size) => setPRF({ page, page_size }) }}
        scroll={{ x: 1400 }}
        expandable={{ expandedRowRender: (r) => r.error_message && <Typography.Paragraph type="danger" style={{ margin: 0 }}><strong>Error:</strong> {r.error_message}</Typography.Paragraph>, rowExpandable: (r) => !!r.error_message }} />
      <Drawer open={dr.open} title={<Space><EyeOutlined /><span>Run Details — {sId(dr.run?.id)}</span></Space>} onClose={() => setDr({ open: false })} width={760} destroyOnClose>
        <RunDrawerContent run={dr.run} />
      </Drawer>
    </div>
  );
};

function RunDrawerContent({ run }: { run?: PipelineRun }) {
  const currentLayer = useMemo(() => deriveCurrentLayer(run), [run]);
  const stats = (run?.stats || {}) as Record<string, any>;
  const layerCounts = LAYER_KEYS.map((k) => ({ key: k, count: (stats?.grades?.[k] ?? stats?.[k] ?? null as number | null) }));

  const layerSteps = useMemo(() => LAYER_KEYS.map((k, i) => {
    const meta = LAYER_LABELS[k];
    const done = currentLayer > i;
    const active = currentLayer === i + 1;
    const cnt = layerCounts[i]?.count;
    return {
      title: (
        <Space direction="vertical" size={2} style={{ padding: '6px 0' }}>
          <Space>
            <span style={{ fontWeight: active ? 600 : 400 }}>{meta.title}</span>
            {active && <Tag color="processing">RUNNING</Tag>}
            {done && <Tag color="success">DONE</Tag>}
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>{meta.desc}</Text>
          {cnt != null && <Text type="secondary" style={{ fontSize: 12 }}>Records: {cnt}</Text>}
        </Space>
      ),
      status: (run?.status === 'failed' && active ? 'error' : done ? 'finish' : active ? 'process' : 'wait') as any,
      icon: meta.icon,
    };
  }), [currentLayer, layerCounts, run?.status]);

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {run?.error_message && (
        <Alert type="error" showIcon message="Pipeline failed" description={<Text code>{run.error_message}</Text>} />
      )}
      <Tabs
        size="small"
        defaultActiveKey="layers"
        items={[
          {
            key: 'layers',
            label: <Space><BranchesOutlined />Layers L1~L6</Space>,
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card size="small" title={<Space><NodeIndexOutlined />Status Timeline</Space>}>
                  <Steps
                    direction="vertical"
                    size="small"
                    current={currentLayer}
                    status={run?.status === 'failed' ? 'error' : undefined}
                    items={layerSteps}
                  />
                </Card>
                <Card size="small" title={<Space><BulbOutlined />Per-layer counts</Space>}>
                  {LAYER_KEYS.every((k) => stats?.[k] == null && stats?.grades?.[k] == null) ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无层级统计数据" />
                  ) : (
                    <Row gutter={[8, 8]}>
                      {LAYER_KEYS.map((k) => {
                        const n = stats?.grades?.[k] ?? stats?.[k] ?? '-';
                        return (
                          <Col key={k} xs={12} md={8}>
                            <Card size="small" style={{ borderLeft: `3px solid ${layerIndexOf(k) < currentLayer ? '#52c41a' : layerIndexOf(k) + 1 === currentLayer ? '#1677ff' : '#d9d9d9'}` }}>
                              <Space direction="vertical" size={2}>
                                <Text strong>{LAYER_LABELS[k]?.title || k}</Text>
                                <Statistic value={n} valueStyle={{ fontSize: 20, color: layerIndexOf(k) < currentLayer ? '#52c41a' : '#1677ff' }} />
                              </Space>
                            </Card>
                          </Col>
                        );
                      })}
                    </Row>
                  )}
                </Card>
              </Space>
            ),
          },
          {
            key: 'l3',
            label: <Space><NodeIndexOutlined />L3 Hasse 概念格</Space>,
            children: (
              <Card size="small" title="L3 FCA 形式概念 Hasse 图（简化树，前 20 概念）">
                <Tree
                  showLine
                  defaultExpandAll
                  treeData={MOCK_L3_HASSE_TREE}
                  style={{ padding: '8px 12px', minHeight: 300 }}
                />
                <Divider style={{ margin: '12px 0' }} />
                <Text type="secondary">
                  <BulbOutlined /> Stability ≥ 0.6 的概念共 12 个，按 is-a 映射为层级边。
                </Text>
              </Card>
            ),
          },
          {
            key: 'l4',
            label: <Space><BranchesOutlined />L4 关系气泡图</Space>,
            children: (
              <Card size="small" title={<>L4 RelationDiscoverer 4 类关系 SVG 气泡图（示意，前 50 条）</>} extra={
                <Space size="small">
                  {(['is-a','part-of','attribute-of','related-to'] as RelBubble['kind'][]).map((k) => (
                    <Tag key={k} color={REL_KIND_COLOR[k]}>{k}</Tag>
                  ))}
                </Space>
              }>
                <svg viewBox="0 0 400 360" width="100%" height={360} style={{ background: '#fafafa', borderRadius: 8 }}>
                  {MOCK_L4_BUBBLES.map((b, i) => (
                    <g key={i}>
                      <circle cx={b.x} cy={b.y} r={b.r} fill={REL_KIND_COLOR[b.kind]} fillOpacity={0.18} stroke={REL_KIND_COLOR[b.kind]} strokeWidth={1} />
                      <text x={b.x} y={b.y + 3} textAnchor="middle" fontSize={Math.max(8, Math.min(11, b.r - 2))} fill="#333">
                        {b.name.length > 6 ? b.name.slice(0, 6) : b.name}
                      </text>
                    </g>
                  ))}
                </svg>
                <Divider style={{ margin: '12px 0' }} />
                <Row gutter={[12, 8]}>
                  <Col span={6}><Statistic title="is-a (继承)" value={MOCK_L4_BUBBLES.filter((b)=>b.kind==='is-a').length} valueStyle={{ color: REL_KIND_COLOR['is-a'] }} /></Col>
                  <Col span={6}><Statistic title="part-of (部分)" value={MOCK_L4_BUBBLES.filter((b)=>b.kind==='part-of').length} valueStyle={{ color: REL_KIND_COLOR['part-of'] }} /></Col>
                  <Col span={6}><Statistic title="attribute-of (属性)" value={MOCK_L4_BUBBLES.filter((b)=>b.kind==='attribute-of').length} valueStyle={{ color: REL_KIND_COLOR['attribute-of'] }} /></Col>
                  <Col span={6}><Statistic title="related-to (关联)" value={MOCK_L4_BUBBLES.filter((b)=>b.kind==='related-to').length} valueStyle={{ color: REL_KIND_COLOR['related-to'] }} /></Col>
                </Row>
              </Card>
            ),
          },
          {
            key: 'json',
            label: <Space><CopyOutlined />Raw JSON</Space>,
            children: (
              <Typography.Text code style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', display: 'block', background: '#f5f5f5', padding: 12, borderRadius: 6 }}>
                {JSON.stringify(run, null, 2)}
              </Typography.Text>
            ),
          },
        ]}
      />
    </Space>
  );
}

export default PipelineRunsPage;
