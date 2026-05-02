import { useEffect, useRef, useState } from 'react';
import { Card, Select, Button, Empty, Input, Dropdown } from 'antd';
import { ReloadOutlined, PlusOutlined, FilterOutlined, SettingOutlined } from '@ant-design/icons';
import { Graph } from '@antv/g6';

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  side?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: GraphNode) => void;
  onEdgeClick?: (edge: GraphEdge) => void;
  onRefresh?: () => void;
}

function GraphToolbar({
  onRefresh,
  mode,
  onModeChange,
  layout,
  onLayoutChange,
  searchText,
  onSearchChange,
}: {
  onRefresh?: () => void;
  mode: 'select' | 'pan' | 'edit';
  onModeChange: (mode: 'select' | 'pan' | 'edit') => void;
  layout: 'force' | 'circular' | 'grid';
  onLayoutChange: (layout: 'force' | 'circular' | 'grid') => void;
  searchText: string;
  onSearchChange: (text: string) => void;
}) {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
      <Dropdown menu={{ items: [
        { key: 'select', label: '选择模式', onClick: () => onModeChange('select') },
        { key: 'pan', label: '平移模式', onClick: () => onModeChange('pan') },
        { key: 'edit', label: '编辑模式', onClick: () => onModeChange('edit') },
      ] }}>
        <Button>
          {mode === 'select' ? '选择模式' : mode === 'pan' ? '平移模式' : '编辑模式'} <SettingOutlined />
        </Button>
      </Dropdown>

      <Dropdown menu={{ items: [
        { key: 'all', label: '显示全部' },
        { key: 'unit', label: '仅显示单元' },
        { key: 'equipment', label: '仅显示装备' },
        { key: 'location', label: '仅显示位置' },
        { key: 'event', label: '仅显示事件' },
      ] }}>
        <Button icon={<FilterOutlined />}>
          筛选
        </Button>
      </Dropdown>

      <Select
        value={layout}
        onChange={onLayoutChange}
        options={[
          { value: 'force', label: '力导向' },
          { value: 'circular', label: '环形' },
          { value: 'grid', label: '网格' },
        ]}
        style={{ width: 100 }}
      />

      <Input.Search
        placeholder="搜索实体"
        value={searchText}
        onChange={(e) => onSearchChange(e.target.value)}
        style={{ width: 160 }}
        allowClear
      />

      <Button icon={<PlusOutlined />}>
        添加
      </Button>

      <Button icon={<ReloadOutlined />} onClick={() => onRefresh?.()}>
        刷新
      </Button>
    </div>
  );
}

const nodeColors: Record<string, string> = {
  Unit: '#1890ff',
  Equipment: '#52c41a',
  Location: '#faad14',
  Event: '#ff4d4f',
  Organization: '#722ed1',
};

const nodeShapes: Record<string, string> = {
  Unit: 'circle',
  Equipment: 'rect',
  Location: 'diamond',
  Event: 'ellipse',
  Organization: 'circle',
};

const sideColors: Record<string, string> = {
  red: '#ff4d4f',
  blue: '#1890ff',
  neutral: '#8c8c8c',
};

const edgeStyles: Record<string, any> = {
  located_at: { stroke: '#8c8c8c', lineWidth: 1, endArrow: false },
  engaged_with: {
    stroke: '#ff4d4f',
    lineWidth: 2,
    lineDash: [5, 5],
    endArrow: {
      type: 'triangle',
      size: 8,
    },
  },
  supports: {
    stroke: '#52c41a',
    lineWidth: 2,
    lineDash: [2, 2],
    endArrow: {
      type: 'triangle',
      size: 6,
    },
  },
  opposes: {
    stroke: '#ff4d4f',
    lineWidth: 2,
    lineDash: [5, 5],
    endArrow: {
      type: 'triangle',
      size: 6,
    },
  },
  attached_to: {
    stroke: '#1890ff',
    lineWidth: 2,
    endArrow: {
      type: 'triangle',
      size: 6,
    },
  },
};

export function GraphCanvas({ nodes, edges, onNodeClick, onEdgeClick, onRefresh }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<'force' | 'circular' | 'grid'>('force');
  const [mode, setMode] = useState<'select' | 'pan' | 'edit'>('select');
  const [searchText, setSearchText] = useState('');
  const graphRef = useRef<Graph | null>(null);

  useEffect(() => {
    let mounted = true;
    let currentGraph: Graph | null = null;

    const initGraph = async () => {
      try {
        if (!containerRef.current || !mounted) return;

        if (graphRef.current) {
          try {
            if (graphRef.current.destroy) {
              graphRef.current.destroy();
            }
          } catch (e) {
            console.warn('销毁旧图实例失败:', e);
          }
          graphRef.current = null;
        }

        const graphData = {
          nodes: nodes.map((n) => ({
            id: n.id,
            data: {
              label: n.name,
              nodeType: n.type,
              side: n.side,
            },
          })),
          edges: edges.map((e) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            data: { edgeType: e.type },
          })),
        };

        const graph = new Graph({
          container: containerRef.current,
          width: containerRef.current.clientWidth,
          height: 600,
          data: graphData,
          node: {
            type: (d: any) => {
              const shape = nodeShapes[d.data?.nodeType];
              return shape || 'circle';
            },
            style: (d: any) => {
              return {
                size: 50,
                fill: nodeColors[d.data?.nodeType] || '#1890ff',
                stroke: sideColors[d.data?.side || 'neutral'],
                lineWidth: 3,
              };
            },
          },
          edge: {
            type: 'line',
            style: (d: any) => {
              const style = edgeStyles[d.data?.edgeType];
              return style || {
                stroke: '#999',
                lineWidth: 2,
              };
            },
          },
          layout: {
            type: layout,
            preventOverlap: true,
            nodeSize: 60,
          }
        });

        if (!mounted) {
          try {
            if (graph.destroy) {
              graph.destroy();
            }
          } catch (e) {
            console.warn('组件已卸载，销毁图实例失败:', e);
          }
          return;
        }

        try {
          graph.render();
        } catch (e) {
          console.error('G6 渲染失败:', e);
          return;
        }

        graph.on('node:click', (evt: any) => {
          if (!mounted) return;
          try {
            const nodeId = evt.item?.get?.('id');
            if (nodeId === undefined || nodeId === null) return;
            const node = nodes.find((n) => n.id === nodeId);
            if (node) onNodeClick?.(node);
          } catch (e) {
            console.warn('节点点击事件处理错误:', e);
          }
        });

        graph.on('edge:click', (evt: any) => {
          if (!mounted) return;
          try {
            const edgeId = evt.item?.get?.('id');
            if (edgeId === undefined || edgeId === null) return;
            const edge = edges.find((e) => e.id === edgeId);
            if (edge) onEdgeClick?.(edge);
          } catch (e) {
            console.warn('边点击事件处理错误:', e);
          }
        });

        currentGraph = graph;
        graphRef.current = graph;
      } catch (error) {
        console.error('G6 初始化失败:', error);
      }
    };

    initGraph();

    return () => {
      mounted = false;
      if (currentGraph) {
        try {
          if (currentGraph.destroy) {
            currentGraph.destroy();
          }
        } catch (e) {
          console.warn('清理 currentGraph 失败:', e);
        }
        currentGraph = null;
      }
      if (graphRef.current) {
        try {
          if (graphRef.current.destroy) {
            graphRef.current.destroy();
          }
        } catch (e) {
          console.warn('清理 graphRef 失败:', e);
        }
        graphRef.current = null;
      }
    };
  }, [nodes, edges, layout, mode, onNodeClick, onEdgeClick]);

  if (nodes.length === 0) {
    return (
      <Card title="本体语义网络" style={{ borderRadius: 8 }}>
        <div style={{ height: 600, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Empty description="暂无语义网络数据，请先通过数据摄入添加实体" />
        </div>
      </Card>
    );
  }

  return (
    <Card
      title="本体语义网络"
      extra={
        <GraphToolbar
          onRefresh={onRefresh}
          mode={mode}
          onModeChange={setMode}
          layout={layout}
          onLayoutChange={setLayout}
          searchText={searchText}
          onSearchChange={setSearchText}
        />
      }
      style={{ borderRadius: 8 }}
    >
      <div
        ref={containerRef}
        style={{ width: '100%', height: 600, background: '#fafafa', borderRadius: 4 }}
      />
    </Card>
  );
}