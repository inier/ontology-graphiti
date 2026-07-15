/**
 * GoalLineage — Goal 父子关系 + ChangeProposal 图（HierarchyGraph 配置化薄包装层）
 *
 * 使用 Cytoscape.js 引擎，dagre TB 布局
 * 保留：Goal 状态着色、Proposal 边点击 Drawer、搜索、导出 PNG、Legend
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Space, Typography, Tag, Drawer, message } from 'antd';
import { HierarchyGraph } from '@/modules/shared/modules/graph';
import type { GraphNode, GraphEdge, NodeStyleConfig, EdgeStyleConfig } from '@/modules/shared/modules/graph';
import { goalApi, type Goal, type GoalLineage as GoalLineageData, type ChangeProposal, type GoalStatus } from '../services/goalApi';
import { ChangeProposalCard } from './ChangeProposalCard';

const { Text } = Typography;

// ─── 类型 ───

export interface GoalLineageProps {
  goalId: string;
  height?: number;
}

// ─── 状态颜色映射 ───

const STATUS_COLOR: Record<GoalStatus, string> = {
  proposed: '#d48806',
  approved: '#1677ff',
  rejected: '#ff4d4f',
  'in-progress': '#52c41a',
  achieved: '#722ed1',
  abandoned: '#8c8c8c',
};

const STATUS_LABEL: Record<GoalStatus, string> = {
  proposed: 'Proposed',
  approved: 'Approved',
  rejected: 'Rejected',
  'in-progress': 'In Progress',
  achieved: 'Achieved',
  abandoned: 'Abandoned',
};

// ─── 样式映射 ───

const NODE_STYLE_MAP: Record<string, NodeStyleConfig> = {
  goal: { fill: '#e6f7ff', stroke: '#1890ff', shape: 'rectangle', size: 60 },
  proposal: { fill: '#f9f0ff', stroke: '#722ed1', shape: 'diamond', size: 50 },
};

const EDGE_STYLE_MAP: Record<string, EdgeStyleConfig> = {
  parent: { stroke: '#1890ff', width: 2, lineDash: [], arrow: true },
  proposal: { stroke: '#722ed1', width: 1.5, lineDash: [4, 3], arrow: true },
};

// ─── 组件 ───

export function GoalLineage({ goalId, height }: GoalLineageProps) {
  const [lineageData, setLineageData] = useState<GoalLineageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedProposal, setSelectedProposal] = useState<ChangeProposal | null>(null);

  // ─── 加载数据 ───
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await goalApi.getLineage(goalId);
      setLineageData(data);
    } catch (error) {
      console.error('加载 Goal 血缘失败', error);
      message.error('加载 Goal 血缘失败');
    } finally {
      setLoading(false);
    }
  }, [goalId]);

  useEffect(() => { loadData(); }, [loadData]);

  // ─── 转换为通用 GraphNode/GraphEdge ───
  const graphNodes: GraphNode[] = useMemo(() => {
    if (!lineageData) return [];
    const nodes: GraphNode[] = [];

    // Goal 节点
    const allGoals = [lineageData.goal, ...(lineageData.ancestors || []), ...(lineageData.children || [])];
    const seen = new Set<string>();
    for (const g of allGoals) {
      if (!g || seen.has(g.id)) continue;
      seen.add(g.id);
      nodes.push({
        id: g.id,
        label: g.title || g.business_objective || g.id,
        type: 'goal',
        properties: { ...g },
      });
    }

    // Proposal 节点
    for (const p of lineageData.proposals || []) {
      nodes.push({
        id: `proposal-${p.id}`,
        label: p.title || p.id,
        type: 'proposal',
        properties: { ...p },
      });
    }

    return nodes;
  }, [lineageData]);

  const graphEdges: GraphEdge[] = useMemo(() => {
    if (!lineageData) return [];
    const edges: GraphEdge[] = [];

    // parent 边
    const allGoals = [lineageData.goal, ...(lineageData.ancestors || []), ...(lineageData.children || [])];
    for (const g of allGoals) {
      if (!g) continue;
      if (g.parent_goal_id) {
        edges.push({
          id: `parent-${g.id}`,
          source: g.parent_goal_id,
          target: g.id,
          type: 'parent',
          label: 'parent',
        });
      }
    }

    // proposal 边
    for (const p of lineageData.proposals || []) {
      if (p.goal_id) {
        edges.push({
          id: `proposal-edge-${p.id}`,
          source: p.goal_id,
          target: `proposal-${p.id}`,
          type: 'proposal',
          label: 'proposal',
        });
      }
    }

    return edges;
  }, [lineageData]);

  // ─── 边点击 → Proposal Drawer ───
  const handleEdgeClick = useCallback((edge: GraphEdge) => {
    if (edge.type === 'proposal' && lineageData) {
      const proposalId = edge.id.replace('proposal-edge-', '');
      const proposal = lineageData.proposals?.find((p) => p.id === proposalId);
      if (proposal) setSelectedProposal(proposal);
    }
  }, [lineageData]);

  // ─── 图例 ───
  const legend = (
    <div style={{ background: 'rgba(255,255,255,0.9)', padding: '8px 12px', borderRadius: 6, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
      <Space orientation="vertical" size={4}>
        <Text strong style={{ fontSize: 12 }}>Goal 状态</Text>
        {Object.entries(STATUS_COLOR).map(([status, color]) => (
          <Space key={status} size={4}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
            <Text style={{ fontSize: 11 }}>{STATUS_LABEL[status as GoalStatus]}</Text>
          </Space>
        ))}
        <Space size={4}>
          <div style={{ width: 10, height: 10, borderRadius: 2, background: '#722ed1', transform: 'rotate(45deg)' }} />
          <Text style={{ fontSize: 11 }}>Proposal</Text>
        </Space>
      </Space>
    </div>
  );

  return (
    <>
      <HierarchyGraph
        title="Goal 血缘关系"
        nodes={graphNodes}
        edges={graphEdges}
        nodeStyleMap={NODE_STYLE_MAP}
        edgeStyleMap={EDGE_STYLE_MAP}
        dagreRankDir="TB"
        defaultLayout="dagre"
        onEdgeClick={handleEdgeClick}
        onRefresh={loadData}
        legend={legend}
        height={height}
        detailPanel={
          <Drawer
            title="ChangeProposal 详情"
            placement="right"
            open={!!selectedProposal}
            onClose={() => setSelectedProposal(null)}
            width={400}
          >
            {selectedProposal && (
              <ChangeProposalCard proposalId={selectedProposal.id} />
            )}
          </Drawer>
        }
      />
    </>
  );
}

export default GoalLineage;
