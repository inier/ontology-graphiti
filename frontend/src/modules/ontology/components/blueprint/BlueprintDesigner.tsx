import { useCallback, useEffect, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
  useReactFlow,
  type NodeTypes,
  type Connection,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Layout, message } from 'antd';
import { useBlueprintStore } from '../../stores/blueprintStore';
import { blueprintApi } from '../../services/blueprintApi';
import { BlueprintNode as BPNode } from './BlueprintNode';
import { BlueprintEdge as BPEdge } from './BlueprintEdge';
import { NodePanel } from './NodePanel';
import { BlueprintToolbar } from './BlueprintToolbar';
import { BlueprintList } from './BlueprintList';
import { NODE_TYPE_CONFIG } from './nodeTypes';

const nodeTypes: NodeTypes = {
  data_source: BPNode,
  transform: BPNode,
  ontology: BPNode,
  action: BPNode,
  validation: BPNode,
  output: BPNode,
  agent: BPNode,
  decision: BPNode,
};

const edgeTypes = {
  data_flow: BPEdge,
  control_flow: BPEdge,
  dependency: BPEdge,
};

function blueprintToFlowNodes(
  nodes: Array<{ node_id: string; node_type: string; name: string; position: { x: number; y: number }; config: Record<string, unknown> }>
): Node[] {
  return nodes.map(n => ({
    id: n.node_id,
    type: n.node_type,
    position: n.position || { x: 0, y: 0 },
    data: { label: n.name, nodeType: n.node_type, config: n.config },
  }));
}

function blueprintToFlowEdges(
  edges: Array<{ edge_id: string; source: string; target: string; edge_type: string; label: string }>
): Edge[] {
  return edges.map(e => ({
    id: e.edge_id,
    source: e.source,
    target: e.target,
    type: e.edge_type || 'data_flow',
    label: e.label,
    data: { edgeType: e.edge_type || 'data_flow' },
  }));
}

function BlueprintDesignerInner() {
  const {
    currentBlueprint,
    loadBlueprints,
    addNode,
    addEdge: storeAddEdge,
    removeNode,
    updateNodePosition,
    batchUpdatePositions,
    setSelectedNodeIds,
    selectedNodeIds,
    validate,
    publish,
    autoLayout,
  } = useBlueprintStore();

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();

  useEffect(() => {
    loadBlueprints();
  }, []);

  useEffect(() => {
    if (currentBlueprint) {
      setNodes(blueprintToFlowNodes(currentBlueprint.nodes));
      setEdges(blueprintToFlowEdges(currentBlueprint.edges));
    } else {
      setNodes([]);
      setEdges([]);
    }
  }, [currentBlueprint]);

  const onConnect = useCallback(
    (connection: Connection) => {
      if (connection.source && connection.target) {
        storeAddEdge(connection.source, connection.target, 'data_flow');
      }
    },
    [storeAddEdge]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const nodeType = event.dataTransfer.getData('application/reactflow');
      if (!nodeType || !currentBlueprint) return;
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      addNode(nodeType, NODE_TYPE_CONFIG[nodeType as keyof typeof NODE_TYPE_CONFIG]?.label || nodeType, position);
    },
    [currentBlueprint, addNode, screenToFlowPosition]
  );

  const onNodeDragStop = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      updateNodePosition(node.id, node.position);
    },
    [updateNodePosition]
  );

  const onSelectionChange = useCallback(
    ({ nodes: selectedNodes }: { nodes: Node[] }) => {
      setSelectedNodeIds(selectedNodes.map(n => n.id));
    },
    [setSelectedNodeIds]
  );

  const handleSave = useCallback(async () => {
    await batchUpdatePositions();
    message.success('蓝图已保存');
  }, [batchUpdatePositions]);

  const handleValidate = useCallback(async () => {
    const result = await validate();
    if (result.is_valid) {
      message.success('蓝图验证通过');
    } else {
      message.error(`验证失败: ${result.errors.join(', ')}`);
    }
    if (result.warnings.length > 0) {
      message.warning(`警告: ${result.warnings.join(', ')}`);
    }
  }, [validate]);

  const handlePublish = useCallback(async () => {
    await publish();
    message.success('蓝图已发布');
  }, [publish]);

  const handleAutoLayout = useCallback(async () => {
    await autoLayout('TB');
    message.success('自动布局完成');
  }, [autoLayout]);

  const handleDeleteSelected = useCallback(async () => {
    for (const nodeId of selectedNodeIds) {
      await removeNode(nodeId);
    }
  }, [selectedNodeIds, removeNode]);

  const handleExport = useCallback(
    async (format: 'json' | 'code') => {
      if (!currentBlueprint) return;
      try {
        const result = await blueprintApi.export(currentBlueprint.blueprint_id, format);
        const content = format === 'json' ? JSON.stringify(result.blueprint, null, 2) : result.code || '';
        const blob = new Blob([content], { type: format === 'json' ? 'application/json' : 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentBlueprint.name}.${format === 'json' ? 'json' : 'py'}`;
        a.click();
        URL.revokeObjectURL(url);
      } catch {
        message.error('导出失败');
      }
    },
    [currentBlueprint]
  );

  return (
    <Layout style={{ height: '100%', background: '#fff' }}>
      <Layout.Sider
        width={260}
        style={{ background: '#fafafa', borderRight: '1px solid #f0f0f0', overflow: 'auto' }}
      >
        <div style={{ padding: 12 }}>
          <BlueprintList />
          <div style={{ marginTop: 16 }}>
            <NodePanel />
          </div>
        </div>
      </Layout.Sider>
      <Layout.Content>
        <BlueprintToolbar
          onSave={handleSave}
          onValidate={handleValidate}
          onPublish={handlePublish}
          onAutoLayout={handleAutoLayout}
          onDeleteSelected={selectedNodeIds.length > 0 ? handleDeleteSelected : undefined}
          onExport={handleExport}
          hasBlueprint={!!currentBlueprint}
        />
        <div ref={reactFlowWrapper} style={{ height: 'calc(100vh - 160px)' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onDragOver={onDragOver}
            onDrop={onDrop}
            onNodeDragStop={onNodeDragStop}
            onSelectionChange={onSelectionChange}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            deleteKeyCode="Delete"
            multiSelectionKeyCode="Shift"
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
      </Layout.Content>
    </Layout>
  );
}

export function BlueprintDesigner() {
  return (
    <ReactFlowProvider>
      <BlueprintDesignerInner />
    </ReactFlowProvider>
  );
}
