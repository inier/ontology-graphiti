import { useState, useEffect, useCallback, useMemo } from 'react';

import { Select, Empty, Card, Spin, message } from 'antd';

import { ApartmentOutlined } from '@ant-design/icons';

import { PageHeader } from '@/modules/shared/components/PageHeader';

import { useWorkspace } from '@/modules/shared/components/LayoutContexts';

import { useI18n } from '@/modules/shared/hooks/useI18n';

import { useOntologyStore } from '../stores/ontologyStore';

import { GraphCanvas } from '@/modules/shared/modules/graph/components/GraphCanvas';

import type { GraphNode, GraphEdge } from '@/modules/shared/modules/graph';

import { NodeEdgeEditor } from '../components/NodeEdgeEditor';



export function OntologyGraphPage() {

  const { t } = useI18n('ontology');

  const { currentWorkspace } = useWorkspace();

  const {

    ontologies,

    currentOntology,

    objectTypes,

    linkTypes,

    loading,

    loadOntologies,

    selectOntology,

    loadGraph,

    graphData,

  } = useOntologyStore();



  const [selectedOntologyId, setSelectedOntologyId] = useState<string | undefined>(

    currentOntology?.ontology_id || undefined,

  );

  const [graphLoading, setGraphLoading] = useState(false);



  // Graph editor state

  const [editorVisible, setEditorVisible] = useState(false);

  const [editorNode, setEditorNode] = useState<GraphNode | undefined>();

  const [editorEdge, setEditorEdge] = useState<GraphEdge | undefined>();



  // Load ontologies filtered by current workspace

  useEffect(() => {

    loadOntologies(currentWorkspace || undefined);

  }, [loadOntologies, currentWorkspace]);



  // Auto-select current ontology

  useEffect(() => {

    if (currentOntology && !selectedOntologyId) {

      setSelectedOntologyId(currentOntology.ontology_id);

    }

  }, [currentOntology, selectedOntologyId]);



  const handleOntologyChange = useCallback(async (ontologyId: string) => {

    setSelectedOntologyId(ontologyId);

    setEditorVisible(false);

    setEditorNode(undefined);

    setEditorEdge(undefined);

    await selectOntology(ontologyId);

  }, [selectOntology]);



  // Load graph data when ontology is selected

  useEffect(() => {

    if (currentOntology) {

      setGraphLoading(true);

      loadGraph().finally(() => setGraphLoading(false));

    }

  }, [currentOntology?.ontology_id]); // eslint-disable-line react-hooks/exhaustive-deps



  const handleRefresh = useCallback(async () => {

    if (currentOntology) {

      setGraphLoading(true);

      try {

        await loadGraph();

        message.success(t('图谱已刷新'));

      } finally {

        setGraphLoading(false);

      }

    }

  }, [currentOntology, loadGraph, t]);



  const handleNodeClick = useCallback((node: GraphNode) => {

    setEditorNode(node);

    setEditorEdge(undefined);

    setEditorVisible(true);

  }, []);



  const handleEdgeClick = useCallback((edge: GraphEdge) => {

    setEditorEdge(edge);

    setEditorNode(undefined);

    setEditorVisible(true);

  }, []);



  const handleEditorClose = useCallback(() => {

    setEditorVisible(false);

    setEditorNode(undefined);

    setEditorEdge(undefined);

  }, []);



  const handleEditorUpdate = useCallback(() => {

    if (currentOntology) loadGraph();

  }, [currentOntology, loadGraph]);



  // Build graph data from store

  const graphNodes: GraphNode[] = useMemo(() => {

    // Try to use graphData from API first, fallback to local construction

    if (graphData && Array.isArray((graphData as Record<string, unknown>).nodes)) {

      return ((graphData as Record<string, unknown>).nodes as Array<Record<string, unknown>>).map((n) => ({

        id: String(n.id),

        label: String(n.name || n.label || n.id),

        type: String(n.type || 'ObjectType'),

        side: n.side ? String(n.side) : undefined,

      }));

    }

    // Fallback: construct from objectTypes

    return objectTypes.map((t) => ({

      id: t.id,

      label: t.display_name || t.name,

      type: 'ObjectType',

    }));

  }, [graphData, objectTypes]);



  const graphEdges: GraphEdge[] = useMemo(() => {

    if (graphData && Array.isArray((graphData as Record<string, unknown>).edges)) {

      return ((graphData as Record<string, unknown>).edges as Array<Record<string, unknown>>).map((e) => ({

        id: String(e.id),

        source: String(e.source),

        target: String(e.target),

        type: String(e.type || e.label || 'related_to'),

      }));

    }

    // Fallback: construct from linkTypes

    return linkTypes

      .filter((l) => l.source_type && l.target_type)

      .map((l) => ({

        id: l.id,

        source: l.source_type!,

        target: l.target_type!,

        type: l.name,

      }));

  }, [graphData, linkTypes]);



  const ontologyOptions = ontologies.map((o) => ({
    label: o.name,
    value: o.ontology_id,
  }));



  return (

    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>

      <PageHeader

        title={t('语义图谱')}

        actions={

          <Select

              value={selectedOntologyId}

              onChange={handleOntologyChange}

              style={{ width: 240 }}

              options={ontologyOptions}

              placeholder={t('选择本体')}

              showSearch

              optionFilterProp="label"

            />

        }

      />



      <div style={{ flex: 1, overflow: 'hidden' }}>

        {!currentOntology ? (

          <Card style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>

            <Empty

              image={<ApartmentOutlined style={{ fontSize: 64, color: '#bfbfbf' }} />}

              description={t('请先选择一个本体以查看语义图谱')}

            />

          </Card>

        ) : graphLoading && graphNodes.length === 0 ? (

          <Card style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>

            <Spin size="large" description={t('加载图谱数据中...')} />

          </Card>

        ) : graphNodes.length === 0 ? (

          <Card style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>

            <Empty description={t('暂无图谱数据，请先定义对象类型和关系类型')} />

          </Card>

        ) : (

          <GraphCanvas

            nodes={graphNodes}

            edges={graphEdges}

            onRefresh={handleRefresh}

            onNodeClick={handleNodeClick}

            onEdgeClick={handleEdgeClick}

          />

        )}

      </div>



      <NodeEdgeEditor

        open={editorVisible}

        onClose={handleEditorClose}

        selectedNode={editorNode as unknown as Record<string, unknown> | undefined}

        selectedEdge={editorEdge as unknown as Record<string, unknown> | undefined}

        ontologyId={currentOntology?.ontology_id || ''}

        onUpdate={handleEditorUpdate}

      />

    </div>

  );

}

