import { useState, useMemo } from 'react';
import {
  Card, Row, Col, Tag, Typography, Button, Modal, Input, Space,
  message, Descriptions, Tooltip, Empty,
} from 'antd';
import {
  ThunderboltOutlined, ApiOutlined, SearchOutlined, ShareAltOutlined,
  MessageOutlined, BarChartOutlined, ApartmentOutlined, ClusterOutlined,
  ExperimentOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useWorkspace } from '@/modules/shared/components/LayoutContexts';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Paragraph, Text } = Typography;

/**
 * 递归翻译对象中所有字符串值（用于 sample 等嵌套结构）。
 */
function translateStrings(obj: unknown, t: (key: string) => string): unknown {
  if (typeof obj === 'string') return t(obj);
  if (Array.isArray(obj)) return obj.map((v) => translateStrings(v, t));
  if (obj && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj).map(([k, v]) => [k, translateStrings(v, t)]),
    );
  }
  return obj;
}

/**
 * 7 个语义检索 MCP 工具目录（镜像后端 semantic_retrieval_tools.py register_all）。
 * FR-010 一致性：MCP 工具与 REST 端点复用同一 RetrievalService，调用结果等价。
 * 前端通过 REST 端点调用（与 MCP 结果一致），便于在浏览器内验证。
 */
interface ToolSpec {
  name: string;
  endpoint: string;
  method: 'POST';
  category: string;
  icon: React.ReactNode;
  color: string;
  desc: string;
  schema: string;
  sample: Record<string, unknown>;
}

const TOOL_SPECS: ToolSpec[] = [
  {
    name: 'ontology_query',
    endpoint: '/api/semantic-retrieval/query',
    method: 'POST',
    category: '统一检索',
    icon: <SearchOutlined />,
    color: '#1677ff',
    desc: '本体统一检索 — 自动路由到最合适的检索引擎 (graph/nl/chain/mdl/metric)。',
    schema: 'query:str (自然语言或结构化查询), mode?:str=auto|chain|nl|mdl|graph|metric, limit?:int=1..200, workspace_id:str',
    sample: { query: '查询所有客户及其订单', mode: 'auto', limit: 20 },
  },
  {
    name: 'ontology_graph',
    endpoint: '/api/semantic-retrieval/graph',
    method: 'POST',
    category: '分项图检索',
    icon: <ShareAltOutlined />,
    color: '#52c41a',
    desc: '本体分项图检索 — 实体/关系图结构查询 (FR-005)。',
    schema: 'query:str (Cypher 片段或实体关键词), limit?:int=1..200 (默认 20), workspace_id:str',
    sample: { query: '客户', limit: 20 },
  },
  {
    name: 'ontology_nl',
    endpoint: '/api/semantic-retrieval/nl',
    method: 'POST',
    category: '分项 NL 检索',
    icon: <MessageOutlined />,
    color: '#722ed1',
    desc: '本体分项 NL 检索 — 自然语言查询 + USL 术语消歧 (FR-003/FR-016)。',
    schema: 'query:str (自然语言), limit?:int=1..200 (默认 20), workspace_id:str',
    sample: { query: '最近一周的新增客户', limit: 20 },
  },
  {
    name: 'ontology_metric',
    endpoint: '/api/semantic-retrieval/metric',
    method: 'POST',
    category: '指标查询',
    icon: <BarChartOutlined />,
    color: '#fa8c16',
    desc: '本体指标查询 — TBox 自动派生统计 count/density/trend。',
    schema: 'metric:str=count|density|trend, object_type?:str, granularity?:str=day|week|month (trend 必填), workspace_id:str',
    sample: { metric: 'count' },
  },
  {
    name: 'ontology_reason',
    endpoint: '/api/semantic-retrieval/chain',
    method: 'POST',
    category: '链式推理',
    icon: <ApartmentOutlined />,
    color: '#eb2f96',
    desc: '本项链式推理 — rules[] 有序传导 + 循环检测 + 规则冲突收集 (FR-014)。',
    schema: 'query:str (起点节点), rules?:list[str], max_depth?:int=1..10, persist_candidates?:bool=false, workspace_id:str',
    sample: { query: '客户A', rules: [], max_depth: 5 },
  },
  {
    name: 'ontology_mdl',
    endpoint: '/api/semantic-retrieval/mdl',
    method: 'POST',
    category: 'MDL/DSL 推理',
    icon: <ClusterOutlined />,
    color: '#13c2c2',
    desc: '本体分项 MDL/DSL 推理 — 复用 HE YAML 模板引用 (FR-004 / US3)。',
    schema: 'query:str (含 template/entity/params 的 YAML 段), persist_candidates?:bool=false, workspace_id:str',
    sample: { query: 'template: customer_t\nentity: Customer' },
  },
  {
    name: 'ontology_hybrid',
    endpoint: '/api/semantic-retrieval/hybrid',
    method: 'POST',
    category: '混合检索',
    icon: <ExperimentOutlined />,
    color: '#fa541c',
    desc: '本体混合检索编排 — 多组件顺序执行 + on_failure 容错 (FR-007/008)。',
    schema: 'components:list[{type,params,on_failure}], merge?:str=concat|interleave|rank (默认 concat), workspace_id:str',
    sample: { components: [{ type: 'graph', params: { query: '客户' } }], merge: 'concat' },
  },
];

const McpToolsPage: React.FC = () => {
  const { t } = useI18n('ontology');
  const { currentWorkspace } = useWorkspace();
  const [invokeTool, setInvokeTool] = useState<ToolSpec | null>(null);
  const [invokeOpen, setInvokeOpen] = useState(false);
  const [paramsText, setParamsText] = useState('');
  const [invoking, setInvoking] = useState(false);
  const [result, setResult] = useState<unknown>(null);

  // 翻译 TOOL_SPECS 中的中文文本（category/desc/schema/sample）
  const tools = useMemo(() => TOOL_SPECS.map((tool) => ({
    ...tool,
    category: t(tool.category),
    desc: t(tool.desc),
    schema: t(tool.schema),
    sample: translateStrings(tool.sample, t) as Record<string, unknown>,
  })), [t]);  

  const handleOpenInvoke = (tool: ToolSpec) => {
    setInvokeTool(tool);
    setParamsText(JSON.stringify(tool.sample, null, 2));
    setResult(null);
    setInvokeOpen(true);
  };

  const handleInvoke = async () => {
    if (!invokeTool) return;
    let payload: Record<string, unknown>;
    try {
      payload = paramsText.trim() ? JSON.parse(paramsText) : {};
    } catch {
      message.error(t('参数 JSON 格式错误'));
      return;
    }
    if (currentWorkspace && !payload.workspace_id) {
      payload.workspace_id = currentWorkspace;
    }
    setInvoking(true);
    try {
      const res = await apiClient.post<unknown>(invokeTool.endpoint, payload);
      setResult(res);
      message.success(t('调用成功'));
    } catch (e) {
      const errMsg = (e as Error).message || t('调用失败');
      setResult({ error: errMsg });
      message.error(errMsg);
    } finally {
      setInvoking(false);
    }
  };

  const toolCards = useMemo(() => tools.map((tool) => (
    <Col key={tool.name} xs={24} sm={12} lg={8} xl={6}>
      <Card
        size="small"
        hoverable
        title={
          <Space>
            <span style={{ color: tool.color }}>{tool.icon}</span>
            <Text strong>{tool.name}</Text>
          </Space>
        }
        extra={<Tag color="blue">{tool.category}</Tag>}
        actions={[
          <Tooltip title={t('通过 REST 调用（与 MCP 结果一致 FR-010）')} key="invoke">
            <Button
              type="link"
              size="small"
              icon={<ThunderboltOutlined />}
              onClick={() => handleOpenInvoke(tool)}
            >
              {t('调用')}
            </Button>
          </Tooltip>,
        ]}
      >
        <Paragraph style={{ marginBottom: 8, minHeight: 44, fontSize: 12 }}>{tool.desc}</Paragraph>
        <Descriptions size="small" column={1} colon={false}>
          <Descriptions.Item label={<ApiOutlined />}>
            <Text code style={{ fontSize: 11 }}>{tool.method} {tool.endpoint}</Text>
          </Descriptions.Item>
        </Descriptions>
        <Paragraph type="secondary" style={{ fontSize: 11, marginBottom: 0 }}>
          <Text strong>input_schema: </Text>{tool.schema}
        </Paragraph>
      </Card>
    </Col>
  )), [t]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ padding: 16 }}>
      <Card
        title={<Space><ThunderboltOutlined /><span>{t('MCP 工具集')}</span><Tag color="geekblue">7 tools</Tag></Space>}
        style={{ marginBottom: 16 }}
      >
        <Paragraph type="secondary" style={{ marginBottom: 0 }}>
          {t('语义检索服务总线通过 MCP Server 暴露 7 个工具，供 AI Agent 调用。每个工具与对应 REST 端点复用同一 RetrievalService（FR-010 一致性），可在此页面直接调用验证。')}
        </Paragraph>
      </Card>
      <Row gutter={[12, 12]}>
        {toolCards}
      </Row>

      <Modal
        title={invokeTool ? `${t('调用')} ${invokeTool.name}` : ''}
        open={invokeOpen}
        onCancel={() => { setInvokeOpen(false); setInvokeTool(null); }}
        onOk={handleInvoke}
        okText={t('调用')}
        confirmLoading={invoking}
        width={720}
        destroyOnClose
      >
        {invokeTool && (
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            <Text code>{invokeTool.method} {invokeTool.endpoint}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>{invokeTool.schema}</Text>
            <Text strong style={{ marginTop: 8 }}>{t('参数 (JSON)')}:</Text>
            <Input.TextArea
              value={paramsText}
              onChange={(e) => setParamsText(e.target.value)}
              rows={10}
              style={{ fontFamily: 'monospace', fontSize: 12 }}
            />
            {currentWorkspace && (
              <Text type="secondary" style={{ fontSize: 11 }}>
                {t('workspace_id 未指定时自动填充当前工作空间')}: {currentWorkspace}
              </Text>
            )}
            {result !== null && (
              <>
                <Text strong style={{ marginTop: 8 }}>{t('结果')}:</Text>
                <pre style={{
                  maxHeight: 320, overflow: 'auto', fontSize: 12,
                  background: '#f6f8fa', padding: 12, borderRadius: 6,
                }}>
                  {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
                </pre>
              </>
            )}
            {result === null && <Empty description={t('尚未调用')} style={{ marginTop: 16 }} />}
          </Space>
        )}
      </Modal>
    </div>
  );
};

export default McpToolsPage;
