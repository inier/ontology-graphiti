import { useEffect, useRef, useState } from 'react';
import { Card, Select, Button, Space } from 'antd';
import { ReloadOutlined, ZoomInOutlined, ZoomOutOutlined, FullscreenOutlined } from '@ant-design/icons';
import { entityColors, relationColors, sideColors } from '../styles/colors';

interface GraphNode {
  id: string;
  name: string;
  type: string;
  side?: string;
  [key: string]: unknown;
}

interface GraphEdge {
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
}

export function GraphCanvas({ nodes, edges, onNodeClick, onEdgeClick }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<'force' | 'circular' | 'grid'>('force');

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return;

    const drawGraph = async () => {
      try {
        const G6 = await import('@antv/g6');

        if (!containerRef.current) return;
        containerRef.current.innerHTML = '';

        const graph = new G6.Graph({
          container: containerRef.current,
          width: containerRef.current.clientWidth,
          height: 600,
          modes: {
            default: ['drag-canvas', 'zoom-canvas', 'drag-node'],
          },
          layout: {
            type: layout,
            preventOverlap: true,
            nodeSize: 40,
          },
          defaultNode: {
            size: 40,
            labelCfg: {
              style: {
                fill: '#262626',
                fontSize: 12,
              },
            },
          },
          defaultEdge: {
            style: {
              stroke: '#d9d9d9',
              lineWidth: 2,
            },
            labelCfg: {
              autoRotate: true,
              style: {
                fill: '#8c8c8c',
                fontSize: 10,
              },
            },
          },
          node: (node: GraphNode) => ({
            id: node.id,
            label: node.name,
            type: 'circle',
            style: {
              fill: entityColors[node.type] || '#1890ff',
              stroke: sideColors[node.side || 'neutral'] || '#8c8c8c',
              lineWidth: 3,
            },
          }),
          edge: (edge: GraphEdge) => ({
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: edge.type,
            style: {
              stroke: relationColors[edge.type] || '#d9d9d9',
              lineDash: edge.type === 'engaged_with' ? [5, 5] : undefined,
            },
          }),
        });

        graph.data({ nodes, edges });
        graph.render();

        graph.on('node:click', (evt: { item: { getModel: () => GraphNode } }) => {
          const node = evt.item.getModel();
          onNodeClick?.(node);
        });

        graph.on('edge:click', (evt: { item: { getModel: () => GraphEdge } }) => {
          const edge = evt.item.getModel();
          onEdgeClick?.(edge);
        });
      } catch (error) {
        console.error('G6 加载失败', error);
      }
    };

    drawGraph();
  }, [nodes, edges, layout, onNodeClick, onEdgeClick]);

  return (
    <Card
      title="本体图谱"
      extra={
        <Space>
          <Select
            value={layout}
            onChange={setLayout}
            options={[
              { value: 'force', label: '力导向' },
              { value: 'circular', label: '环形' },
              { value: 'grid', label: '网格' },
            ]}
            style={{ width: 100 }}
          />
          <Button icon={<ZoomInOutlined />}>放大</Button>
          <Button icon={<ZoomOutOutlined />}>缩小</Button>
          <Button icon={<FullscreenOutlined />}>全屏</Button>
          <Button icon={<ReloadOutlined />}>刷新</Button>
        </Space>
      }
      style={{ borderRadius: 8 }}
    >
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: 600,
          background: '#ffffff',
          borderRadius: 4,
        }}
      />
    </Card>
  );
}
