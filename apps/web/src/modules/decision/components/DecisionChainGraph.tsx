/**
 * 决策溯源因果链可视化（AntV G6 v5）
 *
 * 本期修复的两个存量违规（uiux §9.2 第 1 条）：
 * 1. 删除 `NODE_COLORS` 六个十六进制字面量 + 两处灰色回退 —— G6 不消费 CSS 变量，
 *    因此改由父组件 `theme.useToken()` 取色后经 `nodeColors` prop 传入。
 * 2. `useEffect` 依赖加 `nodeColors` —— 原依赖只有 `[chain]`，切主题/深色模式图不重绘。
 * 另外节点标签不再拼 `outcome` 原文（会把「部分成功」显示成 `partial_success`），
 * 改走 `toDisplayLabel(status, outcome)`。
 */
import React, { useEffect, useMemo, useRef } from 'react';
import { Empty, theme } from 'antd';
import { Graph } from '@antv/g6';
import type { EdgeData, NodeData } from '@antv/g6';
import type { DecisionChain, DecisionRecord } from '../types';
import { toDisplayLabel } from '../utils/displayStatus';

/** 父组件可用 `theme.useToken()` 算好传入；不传则组件内自行解析（G6 画布不吃 CSS 变量） */
export type NodeColors = Record<string, string>;

interface AntdTokenLike {
  colorPrimary: string;
  colorWarning: string;
  colorInfo: string;
  colorSuccess: string;
  colorTextSecondary: string;
  colorTextTertiary: string;
  colorFillSecondary: string;
}

function buildNodeColors(token: AntdTokenLike): NodeColors {
  return {
    center: token.colorPrimary,
    // 上游决策不再用紫色（原 NODE_COLORS.parent 是紫色系，既违规又无业务语义）
    parent: token.colorWarning,
    precedent: token.colorInfo,
    entity: token.colorSuccess,
    // 出处层覆盖率本就受限，用弱化色比高饱和色诚实
    episode: token.colorTextSecondary,
    fallback: token.colorFillSecondary,
    edgeLabel: token.colorTextTertiary,
  };
}

interface Props {
  chain: DecisionChain | null;
  /** 由父级用 antd token 解析后的具体色值 */
  nodeColors?: NodeColors;
  height?: number;
  loading?: boolean;
}

function nodeLabel(record: DecisionRecord): string {
  const { label } = toDisplayLabel(record.status, record.outcome);
  return `${record.recommended_option || record.decision_type || record.decision_id}\n(${label})`;
}

function buildGraphData(chain: DecisionChain): { nodes: NodeData[]; edges: EdgeData[] } {
  const nodes: NodeData[] = [];
  const edges: EdgeData[] = [];
  const center = chain.decision;
  const centerId = center.decision_id;

  nodes.push({ id: centerId, data: { label: nodeLabel(center), nodeType: 'center' } });

  chain.parent_chain.forEach((p) => {
    nodes.push({ id: p.decision_id, data: { label: nodeLabel(p), nodeType: 'parent' } });
    edges.push({ source: p.decision_id, target: centerId, data: { label: 'CAUSED_BY' } });
  });

  chain.precedents.forEach((p) => {
    nodes.push({ id: p.decision_id, data: { label: nodeLabel(p), nodeType: 'precedent' } });
    edges.push({ source: p.decision_id, target: centerId, data: { label: 'PRECEDENT_FOR' } });
  });

  // 证据实体/出处一律显示 name，不把 UUID 当主标签（UUID 对用户零信息量）
  chain.evidence_entities.forEach((e, i) => {
    const id = String(e.uuid || `entity_${i}`);
    nodes.push({ id, data: { label: String(e.name || '未命名实体').slice(0, 24), nodeType: 'entity' } });
    edges.push({ source: id, target: centerId, data: { label: 'DERIVED_FROM' } });
  });

  chain.evidence_episodes.forEach((ep, i) => {
    const id = String(ep.uuid || `episode_${i}`);
    nodes.push({ id, data: { label: String(ep.name || '未命名出处').slice(0, 24), nodeType: 'episode' } });
    edges.push({ source: id, target: centerId, data: { label: 'DERIVED_FROM' } });
  });

  return { nodes, edges };
}

export function DecisionChainGraph({
  chain,
  nodeColors,
  height = 420,
  loading = false,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const { token } = theme.useToken();

  // 稳定引用：避免每次渲染都重建 G6 实例（同时让主题切换成为唯一触发条件）
  const colors = useMemo(
    () =>
      nodeColors ??
      buildNodeColors({
        colorPrimary: token.colorPrimary,
        colorWarning: token.colorWarning,
        colorInfo: token.colorInfo,
        colorSuccess: token.colorSuccess,
        colorTextSecondary: token.colorTextSecondary,
        colorTextTertiary: token.colorTextTertiary,
        colorFillSecondary: token.colorFillSecondary,
      }),
    [
      nodeColors,
      token.colorPrimary,
      token.colorWarning,
      token.colorInfo,
      token.colorSuccess,
      token.colorTextSecondary,
      token.colorTextTertiary,
      token.colorFillSecondary,
    ],
  );

  useEffect(() => {
    if (!containerRef.current || !chain) return;

    const { nodes, edges } = buildGraphData(chain);
    if (graphRef.current) {
      graphRef.current.destroy();
      graphRef.current = null;
    }

    const graph = new Graph({
      container: containerRef.current,
      autoFit: 'view',
      data: { nodes, edges },
      node: {
        style: {
          size: 36,
          fill: (d: NodeData) => colors[String(d.data?.nodeType ?? '')] || colors.fallback,
          labelText: (d: NodeData) => String(d.data?.label ?? d.id ?? ''),
          labelPlacement: 'bottom',
          labelMaxWidth: 140,
          labelFontSize: 10,
        },
      },
      edge: {
        style: {
          endArrow: true,
          labelText: (d: EdgeData) => String(d.data?.label ?? ''),
          labelFontSize: 9,
          labelFill: colors.edgeLabel,
        },
      },
      layout: { type: 'antv-dagre', rankdir: 'BT', nodesep: 40, ranksep: 60 },
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    });
    graphRef.current = graph;
    graph.render();

    return () => {
      graph.destroy();
      graphRef.current = null;
    };
    // 依赖必须含 colors：否则切主题不重绘
  }, [chain, colors]);

  if (loading) {
    return (
      <div
        style={{
          height,
          borderRadius: 'var(--odap-radius-md)',
          background: 'var(--odap-color-bg-tertiary)',
        }}
        aria-label="因果链加载中"
      />
    );
  }

  if (!chain) {
    return <Empty description="没有上游因果链记录" style={{ padding: 48 }} />;
  }
  return <div ref={containerRef} style={{ width: '100%', height }} />;
}
