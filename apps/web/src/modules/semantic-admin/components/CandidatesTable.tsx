import React, { useMemo } from 'react';
import { Table, Tag, Progress, Tooltip, Button, Space, Popconfirm, Descriptions } from 'antd';
import type { TableProps } from 'antd';
import { CheckOutlined, CloseOutlined, DeleteOutlined, CloudServerOutlined, PartitionOutlined } from '@ant-design/icons';
import type { Candidate } from '../services/pipelineApi';
import { SEMANTIC_TYPE_COLOR } from '../types';
import type { GraphitiWritebackStatus } from '../types';

const TIER_COLOR: Record<string, string> = { HIGH: 'green', MEDIUM: 'blue', LOW: 'gold', VERY_LOW: 'red' };
const STATUS_COLOR: Record<string, string> = { new: 'default', gated: 'default', approved: 'green', rejected: 'red', written: 'geekblue', auditor_approved: 'blue', admin_pending: 'orange', written_back: 'purple', stoplisted: 'black' };

interface CTProps {
  data: Candidate[]; loading: boolean; total: number; page: number; pageSize: number;
  selectedIds: string[]; canWrite: boolean;
  onPageChange: (p: number, ps: number) => void; onSelectionChange: (ids: string[]) => void;
  onApproveL1: (c: Candidate) => void; onApproveL2: (c: Candidate) => void;
  onReject: (c: Candidate) => void; onDelete: (c: Candidate) => void;
  onRowClick?: (c: Candidate) => void;
}

const sColor = (s?: string): string => !s ? 'default' : (SEMANTIC_TYPE_COLOR as Record<string, string>)[s] ?? 'default';
const shortId = (id?: string): string => !id ? '-' : id.length > 10 ? `${id.slice(0, 6)}...${id.slice(-4)}` : id;
const fmtDate = (s?: string): string => !s ? '-' : s.substring(0, 19).replace('T', ' ');
const canL1 = (s: string) => ['new', 'gated', 'audited'].includes(s);
const canL2 = (s: string) => s === 'admin_pending';

const renderUslTag = (r: Candidate) => {
  const id = r.provenance?.writeback_usl_term_id;
  if (!id) {
    return <Tag>—</Tag>;
  }
  return (
    <Tooltip title={`USL Term: ${id}`}>
      <Tag color="green" icon={<CloudServerOutlined />} style={{ marginBottom: 0 }}>
        WRITTEN <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{shortId(id)}</span>
      </Tag>
    </Tooltip>
  );
};

const renderGraphitiTag = (r: Candidate) => {
  const gw = r.provenance?.graphiti_writeback as GraphitiWritebackStatus | undefined;
  const oid = r.provenance?.graphiti_ontology_id as string | undefined;
  const tid = r.provenance?.graphiti_type_id as string | undefined;
  if (!gw && !oid && !tid) {
    return <Tag>—</Tag>;
  }
  const st = gw?.status ?? (tid ? 'ok' : undefined);
  if (!st) {
    return <Tag color="default">pending</Tag>;
  }
  const colorMap: Record<string, string> = {
    ok: gw?.skipped ? 'gold' : (gw?.overwrote_existing ? 'geekblue' : 'green'),
    skipped: 'gold',
    error: 'red',
  };
  const iconMap: Record<string, string> = { ok: '✓', skipped: '∘', error: '✗' };
  const labelMap: Record<string, string> = { ok: '写入', skipped: '跳过', error: '失败' };
  const methodBadge = gw?.method ? <Tag style={{ marginLeft: 4, padding: '0 4px' }}>{gw.method}</Tag> : null;
  const tip = [
    oid && `Ontology=${oid}`,
    tid && `TypeID=${tid}`,
    gw?.created_new != null && `created_new=${gw.created_new}`,
    gw?.skipped != null && `skipped=${gw.skipped}`,
    gw?.message ?? '',
  ].filter(Boolean).join('\n');
  return (
    <Tooltip title={tip || undefined}>
      <Tag color={colorMap[st] ?? 'default'} icon={<PartitionOutlined />}>
        {iconMap[st] ?? ''} {labelMap[st] ?? st}
        {methodBadge}
      </Tag>
    </Tooltip>
  );
};

const CandidatesTable: React.FC<CTProps> = (P) => {
  const rowSel: TableProps<Candidate>['rowSelection'] = useMemo(
    () => ({ selectedRowKeys: P.selectedIds, onChange: (k) => P.onSelectionChange(k.map(String)) }),
    [P.selectedIds, P.onSelectionChange, P],
  );

  const cols: TableProps<Candidate>['columns'] = [
    { title: 'Canonical', dataIndex: 'canonical', key: 'c', width: 220, render: (v: string, r) => (
      <div><strong>{v}</strong>{r.stoplist_flag && <Tag color="black" style={{ marginLeft: 6 }}>STOP</Tag>}</div>
    )},
    { title: 'Semantic Type', dataIndex: 'semantic_type', key: 'st', width: 120, render: (v?: string) => v ? <Tag color={sColor(v)}>{v}</Tag> : '-' },
    { title: 'Confidence', dataIndex: 'confidence', key: 'cf', width: 160, render: (v: number) => <Progress percent={Math.round(v * 100)} size="small" /> },
    { title: 'Quality Tier', key: 't', width: 110, render: (_, r) => r.quality_report?.tier ? <Tag color={TIER_COLOR[r.quality_report.tier]}>{r.quality_report.tier}</Tag> : '-' },
    { title: 'Status', dataIndex: 'status', key: 's', width: 140, render: (v: string) => <Tag color={STATUS_COLOR[v] ?? 'default'}>{v}</Tag> },
    { title: 'USL 写回', key: 'usl_wb', width: 160, render: (_: any, r) => renderUslTag(r) },
    { title: 'Graphiti 写回', key: 'g_wb', width: 170, render: (_: any, r) => renderGraphitiTag(r) },
    { title: 'Domain ID', dataIndex: 'domain_id', key: 'did', width: 110, render: (v?: string) => <Tooltip title={v}><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{shortId(v)}</span></Tooltip> },
    { title: 'Created', dataIndex: 'created_at', key: 'ca', width: 160, render: (v: string) => fmtDate(v) },
    { title: 'Actions', key: 'a', width: 260, fixed: 'right', render: (_, r) => (
      <Space size={4}>
        <Button type="link" size="small" icon={<CheckOutlined />} disabled={!P.canWrite || !canL1(r.status)} onClick={() => P.onApproveL1(r)}>Approve L1</Button>
        <Button type="link" size="small" icon={<CheckOutlined />} disabled={!P.canWrite || !canL2(r.status)} onClick={() => P.onApproveL2(r)}>Approve L2</Button>
        <Button type="link" size="small" danger icon={<CloseOutlined />} disabled={!P.canWrite} onClick={() => P.onReject(r)}>Reject</Button>
        <Popconfirm title="Delete this candidate?" okText="Delete" okButtonProps={{ danger: true }} cancelText="Cancel" disabled={!P.canWrite} onConfirm={() => P.onDelete(r)}>
          <Button type="link" size="small" danger icon={<DeleteOutlined />} disabled={!P.canWrite}>Delete</Button>
        </Popconfirm>
      </Space>
    )},
  ];

  return (
    <Table<Candidate> rowKey="id" loading={P.loading} dataSource={P.data} columns={cols} rowSelection={rowSel}
      pagination={{ current: P.page, pageSize: P.pageSize, total: P.total, showSizeChanger: true, showQuickJumper: true, showTotal: (t) => `Total ${t} items`, onChange: P.onPageChange }}
      scroll={{ x: 1680 }}
      onRow={(r) => ({
        onClick: () => P.onRowClick?.(r),
        style: { cursor: P.onRowClick ? 'pointer' : 'default' },
      })}
      expandable={{ expandedRowRender: (r) => {
        const gw = r.provenance?.graphiti_writeback as GraphitiWritebackStatus | undefined;
        const uslTid = r.provenance?.writeback_usl_term_id;
        const oid = r.provenance?.graphiti_ontology_id;
        const tid = r.provenance?.graphiti_type_id;
        const promotedBy = r.provenance?.promoted_by_admin;
        return (
          <div style={{ padding: '4px 12px' }}>
            {r.definition && <p style={{ color: '#888', margin: '4px 0' }}><strong>Definition: </strong>{r.definition}</p>}
            {r.synonyms?.length > 0 && <div style={{ margin: '4px 0' }}><strong>Synonyms: </strong>{r.synonyms.map((s) => <Tag key={s} color="blue" style={{ margin: 2 }}>{s}</Tag>)}</div>}
            {r.aliases?.length > 0 && <div style={{ margin: '4px 0' }}><strong>Aliases: </strong>{r.aliases.map((s) => <Tag key={s} color="geekblue" style={{ margin: 2 }}>{s}</Tag>)}</div>}
            {r.near_synonyms?.length > 0 && <div style={{ margin: '4px 0' }}><strong>Near-synonyms: </strong>{r.near_synonyms.map((s) => <Tag key={s} color="default" style={{ margin: 2 }}>{s}</Tag>)}</div>}
            {(uslTid || oid || tid || gw || promotedBy) ? (
              <Descriptions size="small" column={2} bordered style={{ marginTop: 8 }} title="双写回状态 (Writeback)">
                {promotedBy && <Descriptions.Item label="操作人">{String(promotedBy)}</Descriptions.Item>}
                {uslTid && <Descriptions.Item label="USL Term ID" contentStyle={{ fontFamily: 'monospace', fontSize: 12 }}>{uslTid}</Descriptions.Item>}
                {oid && <Descriptions.Item label="Ontology ID" contentStyle={{ fontFamily: 'monospace', fontSize: 12 }}>{String(oid)}</Descriptions.Item>}
                {tid && <Descriptions.Item label="Graphiti Type ID" contentStyle={{ fontFamily: 'monospace', fontSize: 12 }}>{String(tid)}</Descriptions.Item>}
                {gw?.method && <Descriptions.Item label="写入方法">{gw.method}</Descriptions.Item>}
                {gw && <Descriptions.Item label="写入结果">
                  {gw.status === 'ok' && <Tag color="green">成功</Tag>}
                  {gw.status === 'skipped' && <Tag color="gold">跳过</Tag>}
                  {gw.status === 'error' && <Tag color="red">失败</Tag>}
                  {gw.created_new && <Tag style={{ marginLeft: 4 }}>新建</Tag>}
                  {gw.overwrote_existing && <Tag color="geekblue" style={{ marginLeft: 4 }}>覆盖</Tag>}
                  {gw.skipped && <Tag color="default" style={{ marginLeft: 4 }}>幂等跳过</Tag>}
                </Descriptions.Item>}
                {(gw?.step || gw?.message || gw?.reason) && <Descriptions.Item label="详情" span={2}>
                  {gw.step && <div>step: {gw.step}</div>}
                  {gw.message && <div>msg: {gw.message}</div>}
                  {gw.reason && <div>reason: {gw.reason}</div>}
                </Descriptions.Item>}
              </Descriptions>
            ) : null}
            {r.source_text && <p style={{ color: '#999', margin: '8px 0 0', fontSize: 12 }}><strong>Source: </strong>{r.source_text}</p>}
          </div>
        );
      } }} />
  );
};

export default CandidatesTable;
