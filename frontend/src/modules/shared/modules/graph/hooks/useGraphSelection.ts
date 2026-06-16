/**
 * useGraphSelection — 图谱选中状态管理 hook
 *
 * 管理：选中节点、关联高亮、dim 状态
 */
import { useState, useCallback } from 'react';
import type { GraphNode } from '../types';

interface UseGraphSelectionOptions {
  onNodeSelect?: (node: GraphNode | null) => void;
  onEdgeSelect?: (edgeId: string | null) => void;
}

interface UseGraphSelectionReturn {
  selectedNodeId: string | null;
  selectedNode: GraphNode | null;
  setSelectedNode: (node: GraphNode | null) => void;
  clearSelection: () => void;
}

export function useGraphSelection({
  onNodeSelect,
}: UseGraphSelectionOptions = {}): UseGraphSelectionReturn {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedNode, setSelectedNodeData] = useState<GraphNode | null>(null);

  const setSelectedNode = useCallback((node: GraphNode | null) => {
    setSelectedNodeId(node?.id ?? null);
    setSelectedNodeData(node);
    onNodeSelect?.(node);
  }, [onNodeSelect]);

  const clearSelection = useCallback(() => {
    setSelectedNodeId(null);
    setSelectedNodeData(null);
    onNodeSelect?.(null);
  }, [onNodeSelect]);

  return {
    selectedNodeId,
    selectedNode,
    setSelectedNode,
    clearSelection,
  };
}
