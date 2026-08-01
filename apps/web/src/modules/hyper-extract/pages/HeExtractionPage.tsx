import { useState, useEffect, useCallback } from 'react';
import {
  Card, Tabs, Form, Input, Button, Select, Space, message, Modal,
  Descriptions, Statistic, Row, Col, Empty, Spin, Tag, Typography, Divider,
} from 'antd';
import {
  ThunderboltOutlined, EyeOutlined, ClearOutlined, DatabaseOutlined,
  ClusterOutlined, ClockCircleOutlined, ExperimentOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useWorkspace } from '@/modules/shared/components/LayoutContexts';
import { useOntologyStore } from '@/modules/ontology/stores/ontologyStore';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface ExtractResult {
  status: string;
  entities_count: number;
  relations_count: number;
  valid_time?: string;
  message?: string;
}

interface BatchResult {
  status: string;
  total?: number;
  succeeded?: number;
  failed?: number;
  results?: ExtractResult[];
  message?: string;
}

const HeExtractionPage: React.FC = () => {
  const { t } = useI18n('ontology');
  const { currentWorkspace } = useWorkspace();
  const { ontologies, loadOntologies } = useOntologyStore();

  const [ontologyId, setOntologyId] = useState<string | undefined>();
  const [text, setText] = useState('');
  const [scenarioId, setScenarioId] = useState<string>('');
  const [extracting, setExtracting] = useState(false);
  const [result, setResult] = useState<ExtractResult | null>(null);

  const [templateOpen, setTemplateOpen] = useState(false);
  const [template, setTemplate] = useState<Record<string, unknown> | null>(null);
  const [templateLoading, setTemplateLoading] = useState(false);

  const [batchTexts, setBatchTexts] = useState<string>('');
  const [batching, setBatching] = useState(false);
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);

  useEffect(() => {
    loadOntologies(currentWorkspace || undefined);
  }, [loadOntologies, currentWorkspace]);

  const ontologyOptions = ontologies.map((o) => ({
    label: `${o.name} (${o.ontology_id.slice(0, 8)})`,
    value: o.ontology_id,
  }));

  const handleExtract = useCallback(async () => {
    if (!ontologyId) { message.warning(t('请先选择本体')); return; }
    if (!text.trim()) { message.warning(t('请输入待抽取文本')); return; }
    setExtracting(true);
    try {
      const res = await apiClient.post<ExtractResult>('/api/he/extract', {
        text, ontology_id: ontologyId,
        scenario_id: scenarioId || undefined,
        workspace_id: currentWorkspace || undefined,
      });
      setResult(res);
      if (res.status === 'error') {
        message.error(res.message || t('抽取失败'));
      } else {
        message.success(t('抽取完成'));
      }
    } catch (e) {
      message.error((e as Error).message || t('抽取失败'));
      setResult(null);
    } finally {
      setExtracting(false);
    }
  }, [ontologyId, text, scenarioId, currentWorkspace, t]);

  const handleViewTemplate = useCallback(async () => {
    if (!ontologyId) { message.warning(t('请先选择本体')); return; }
    setTemplateLoading(true);
    setTemplateOpen(true);
    try {
      const res = await apiClient.get<{ ontology_id: string; template: Record<string, unknown> }>(
        `/api/he/templates/${encodeURIComponent(ontologyId)}`,
      );
      setTemplate(res.template || {});
    } catch (e) {
      message.error((e as Error).message || t('模板加载失败'));
      setTemplate(null);
    } finally {
      setTemplateLoading(false);
    }
  }, [ontologyId, t]);

  const handleBatch = useCallback(async () => {
    if (!ontologyId) { message.warning(t('请先选择本体')); return; }
    const texts = batchTexts.split(/\n\s*---\s*\n/).map((s) => s.trim()).filter(Boolean);
    if (texts.length === 0) { message.warning(t('请输入至少一段文本（以 --- 分隔）')); return; }
    setBatching(true);
    try {
      const res = await apiClient.post<BatchResult>('/api/he/extract/batch', {
        texts, ontology_id: ontologyId,
        scenario_id: scenarioId || undefined,
        workspace_id: currentWorkspace || undefined,
      });
      setBatchResult(res);
      if (res.status === 'error') message.error(res.message || t('批量抽取失败'));
      else message.success(t('批量抽取完成'));
    } catch (e) {
      message.error((e as Error).message || t('批量抽取失败'));
      setBatchResult(null);
    } finally {
      setBatching(false);
    }
  }, [ontologyId, batchTexts, scenarioId, currentWorkspace, t]);

  const handleClear = () => {
    setText(''); setResult(null); setBatchTexts(''); setBatchResult(null);
  };

  return (
    <div style={{ padding: 16 }}>
      <Card
        title={<Space><ExperimentOutlined /><span>{t('HE 抽取链')}</span></Space>}
        extra={
          <Space>
            <Button icon={<EyeOutlined />} onClick={handleViewTemplate} disabled={!ontologyId}>
              {t('查看 HE 模板')}
            </Button>
            <Button icon={<ClearOutlined />} onClick={handleClear}>{t('清空')}</Button>
          </Space>
        }
      >
        <Paragraph type="secondary" style={{ marginBottom: 16 }}>
          {t('Hyper-Extract 抽取链：文本 → HE 模板抽取 → 本体映射 → 双通道写入（SQLite + Graphiti）。支持单文本与批量抽取。')}
        </Paragraph>
        <Form layout="vertical">
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label={t('目标本体')} required>
                <Select
                  value={ontologyId}
                  onChange={setOntologyId}
                  options={ontologyOptions}
                  placeholder={t('选择本体')}
                  showSearch
                  optionFilterProp="label"
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label={t('场景 ID（可选）')}>
                <Input value={scenarioId} onChange={(e) => setScenarioId(e.target.value)} placeholder="scenario_id" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label={t('工作空间')}>
                <Input value={currentWorkspace || ''} disabled />
              </Form.Item>
            </Col>
          </Row>
        </Form>

        <Tabs
          items={[
            {
              key: 'single',
              label: <span><ThunderboltOutlined /> {t('单文本抽取')}</span>,
              children: (
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <TextArea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    rows={8}
                    placeholder={t('粘贴待抽取文本…')}
                  />
                  <Button
                    type="primary" icon={<ThunderboltOutlined />}
                    loading={extracting} onClick={handleExtract}
                  >
                    {t('触发抽取')}
                  </Button>
                  {result && (
                    <Card size="small" title={t('抽取结果')}>
                      <Row gutter={16}>
                        <Col span={6}>
                          <Statistic title={t('状态')} valueRender={() =>
                            <Tag color={result.status === 'success' ? 'green' : 'red'}>{result.status}</Tag>
                          } />
                        </Col>
                        <Col span={6}>
                          <Statistic title={t('实体数')} value={result.entities_count} prefix={<DatabaseOutlined />} />
                        </Col>
                        <Col span={6}>
                          <Statistic title={t('关系数')} value={result.relations_count} prefix={<ClusterOutlined />} />
                        </Col>
                        <Col span={6}>
                          <Statistic title={t('有效时间')} value={result.valid_time || '-'} prefix={<ClockCircleOutlined />} />
                        </Col>
                      </Row>
                      {result.message && <Text type="secondary">{result.message}</Text>}
                    </Card>
                  )}
                </Space>
              ),
            },
            {
              key: 'batch',
              label: <span><DatabaseOutlined /> {t('批量抽取')}</span>,
              children: (
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <Text type="secondary">{t('多段文本以单独一行 --- 分隔，每段触发一次抽取。')}</Text>
                  <TextArea
                    value={batchTexts}
                    onChange={(e) => setBatchTexts(e.target.value)}
                    rows={10}
                    placeholder={t('第一段文本…\n---\n第二段文本…')}
                  />
                  <Button
                    type="primary" icon={<ThunderboltOutlined />}
                    loading={batching} onClick={handleBatch}
                  >
                    {t('批量抽取')}
                  </Button>
                  {batchResult && (
                    <Card size="small" title={t('批量结果')}>
                      <Descriptions size="small" column={3} bordered>
                        <Descriptions.Item label={t('状态')}>
                          <Tag color={batchResult.status === 'success' ? 'green' : 'red'}>{batchResult.status}</Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label={t('总数')}>{batchResult.total ?? '-'}</Descriptions.Item>
                        <Descriptions.Item label={t('成功/失败')}>
                          {batchResult.succeeded ?? 0} / {batchResult.failed ?? 0}
                        </Descriptions.Item>
                      </Descriptions>
                      {batchResult.results && batchResult.results.length > 0 && (
                        <>
                          <Divider style={{ margin: '12px 0' }} />
                          {batchResult.results.map((r, i) => (
                            <Tag key={i} color={r.status === 'success' ? 'green' : 'red'} style={{ marginBottom: 4 }}>
                              #{i + 1} {t('实体')}: {r.entities_count} {t('关系')}: {r.relations_count}
                            </Tag>
                          ))}
                        </>
                      )}
                    </Card>
                  )}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title={t('HE 模板（由本体定义生成）')}
        open={templateOpen}
        onCancel={() => setTemplateOpen(false)}
        footer={null}
        width={720}
      >
        {templateLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : template && Object.keys(template).length > 0 ? (
          <pre style={{ maxHeight: 480, overflow: 'auto', fontSize: 12, background: '#f6f8fa', padding: 12, borderRadius: 6 }}>
            {JSON.stringify(template, null, 2)}
          </pre>
        ) : (
          <Empty description={t('无模板数据')} />
        )}
      </Modal>
    </div>
  );
};

export default HeExtractionPage;
