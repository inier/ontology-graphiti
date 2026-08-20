/**
 * 决策溯源因果链可视化（ADR-076 §8 前端块 1，AntV G6 v5）
 * 布局：中心决策节点，上游 CAUSE 链 / 先例 / 证据实体环绕
 */
import React, { useEffect, useRef } from 'react';
import { Empty } from 'antd';
import { Graph } from '@antv/g6';
import type { DecisionChain } from '../types';

interface Props {
  chain: DecisionChain | null;
}

const NODE_COLORS: Record<string, string> = {
  center: '#1677ff',
  parent: '#722ed1',
  precedent: '#13c2c2',
  entity: '#52c41a',
  episode: '#fa8c16',
};

interface G6NodeData {
  id: string;
  data: { label: string; nodeType: string };
}

interface G6EdgeData {
  source: string;
  target: string;
  data: { label: string };
}

function buildGraphData(chain: DecisionChain): { nodes: G6NodeData[]; edges: G6EdgeData[] } {
  const nodes: G6NodeData[] = [];
  const edges: G6EdgeData[] = [];
  const center = chain.decision;
  const centerId = center.decision_id;

  nodes.push({
    id: centerId,
    data: {
      label: `${center.recommended_option || center.decision_type}\n(${center.outcome})`,
      nodeType: 'center',
    },
  });

  // 上游因果链：parent -[:CAUSED_BY]<- center，图上按 parent → center 方向展示
  chain.parent_chain.forEach((p) => {
    nodes.push({
      id: p.decision_id,
      data: { label: `${p.recommended_option || p.decision_id}\n(${p.outcome})`, nodeType: 'parent' },
    });
    edges.push({ source: p.decision_id, target: centerId, data: { label: 'CAUSED_BY' } });
  });

  // 先例：precedent -[:PRECEDENT_FOR]-> center
  chain.precedents.forEach((p) => {
    nodes.push({
      id: p.decision_id,
      data: { label: `${p.recommended_option || p.decision_id}\n(${p.outcome})`, nodeType: 'precedent' },
    });
    edges.push({ source: p.decision_id, target: centerId, data: { label: 'PRECEDENT_FOR' } });
  });

  // 证据实体
  chain.evidence_entities.forEach((e, i) => {
    const id = String(e.uuid || `entity_${i}`);
    nodes.push({
      id,
      data: { label: String(e.name || id).slice(0, 24), nodeType: 'entity' },
    });
    edges.push({ source: id, target: centerId, data: { label: 'DERIVED_FROM' } });
  });

  // 证据 Episode
  chain.evidence_episodes.forEach((ep, i) => {
    const id = String(ep.uuid || `episode_${i}`);
    nodes.push({
      id,
      data: { label: String(ep.name || id).slice(0, 24), nodeType: 'episode' },
    });
    edges.push({ source: id, target: centerId, data: { label: 'DERIVED_FROM' } });
  });

  return { nodes, edges };
}

export function DecisionChainGraph({ chain }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);

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
          fill: (d: any) => NODE_COLORS[d.data?.nodeType] || '#999',
          labelText: (d: any) => d.data?.label || d.id,
          labelPlacement: 'bottom',
          labelMaxWidth: 140,
          labelFontSize: 10,
        },
      },
      edge: {
        style: {
          endArrow: true,
          labelText: (d: any) => d.data?.label || '',
          labelFontSize: 9,
          labelFill: '#888',
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
  }, [chain]);

  if (!chain) {
    return <Empty description="输入决策 ID 查看因果链" style={{ padding: 48 }} />;
  }
  return <div ref={containerRef} style={{ width: '100%', height: 420 }} />;
}
