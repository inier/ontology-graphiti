import type { EdgeProps } from '@xyflow/react';
import { BaseEdge, getBezierPath } from '@xyflow/react';

const EDGE_STYLES: Record<string, { strokeDasharray?: string; stroke?: string }> = {
  data_flow: { stroke: '#1890ff' },
  control_flow: { strokeDasharray: '8 4', stroke: '#722ed1' },
  dependency: { strokeDasharray: '3 3', stroke: '#faad14' },
};

export function BlueprintEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  style = {},
  markerEnd,
}: EdgeProps) {
  const edgeType = (data as Record<string, unknown> | undefined)?.edgeType as string || 'data_flow';
  const typeStyle = EDGE_STYLES[edgeType] || EDGE_STYLES.data_flow;

  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  return (
    <BaseEdge
      id={id}
      path={edgePath}
      markerEnd={markerEnd}
      style={{ ...style, ...typeStyle, strokeWidth: 2 }}
    />
  );
}
