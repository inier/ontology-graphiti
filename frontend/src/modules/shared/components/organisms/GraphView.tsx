import type { FC, CSSProperties } from 'react';
import { useEffect, useRef, useCallback } from 'react';

interface GraphNode {
  id: string;
  label?: string;
  [key: string]: unknown;
}

interface GraphEdge {
  source: string;
  target: string;
  label?: string;
  [key: string]: unknown;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface GraphViewProps {
  data?: GraphData;
  width?: number;
  height?: number;
  fitView?: boolean;
  onNodeClick?: (node: GraphNode) => void;
  onEdgeClick?: (edge: GraphEdge) => void;
  className?: string;
  style?: CSSProperties;
}

const GraphView: FC<GraphViewProps> = ({
  data,
  width = 800,
  height = 600,
  onNodeClick,
  onEdgeClick,
  className,
  style,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null);

  const initGraph = useCallback(async () => {
    if (!containerRef.current) return;

    try {
      const G6 = await import('@antv/g6');
      const instance = new G6.Graph({
        container: containerRef.current,
        width,
        height,
        data: data || { nodes: [], edges: [] },
        autoFit: 'view',
      });

      instance.render();

      if (onNodeClick) {
        instance.on('node:click', (evt: unknown) => {
          const e = evt as { target?: { getModel?: () => GraphNode } };
          const model = e.target?.getModel?.();
          if (model) onNodeClick(model);
        });
      }

      if (onEdgeClick) {
        instance.on('edge:click', (evt: unknown) => {
          const e = evt as { target?: { getModel?: () => GraphEdge } };
          const model = e.target?.getModel?.();
          if (model) onEdgeClick(model);
        });
      }

      graphRef.current = instance;
    } catch {
      if (containerRef.current) {
        containerRef.current.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#999;">Graph visualization requires @antv/g6</div>';
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width, height]);

  useEffect(() => {
    initGraph();

    return () => {
      if (graphRef.current) {
        graphRef.current.destroy();
        graphRef.current = null;
      }
    };
  }, [initGraph]);

  useEffect(() => {
    if (graphRef.current && data) {
      graphRef.current.setData(data);
      graphRef.current.render();
    }
  }, [data]);

  return (
    <div className={className} style={{ width, height, ...style }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
};

export default GraphView;
