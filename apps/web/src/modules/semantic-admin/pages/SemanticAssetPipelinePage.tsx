/**
 * 语义资产 Pipeline 向导页（/semantic-admin/assets）
 *
 * 一条 Pipeline 完成语义定义全流程：
 *   Step 0 选择本体（可选，约束性抽取必填）
 *   Step 1 选择数据源类型（结构化引入 / 非结构化抽取）
 *   Step 2 选择/配置抽取模板（非结构化链路）
 *   Step 3 执行抽取 → 候选归集
 *   Step 4 提交审核
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  message,
  Radio,
  Row,
  Select,
  Space,
  Steps,
  Table,
  Tag,
  Typography,
} from 'antd';
import {
  ApartmentOutlined,
  CheckCircleOutlined,
  CloudUploadOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { SemanticAdminTabsContainer } from './SemanticAdminIndex';
import {
  getAssetPipelineOptions,
  runAssetPipeline,
  submitAssetPipeline,
  type AssetPipelineOptions,
  type AssetPipelineRunResult,
  type AssetTemplate,
  type AssetOntology,
  type AssetCandidate,
} from '../services/assetPipelineApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Title, Paragraph } = Typography;

type StepKey = 0 | 1 | 2 | 3;

interface StepState {
  ontologyId?: string;
  sourceType?: string;
  extractionMode?: 'constrained' | 'exploratory';
  templateRef?: string;
}

export default function SemanticAssetPipelinePage() {
  const { t } = useI18n();
  const [current, setCurrent] = useState<StepKey>(0);
  const [options, setOptions] = useState<AssetPipelineOptions | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [running, setRunning] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [state, setState] = useState<StepState>({
    extractionMode: 'exploratory',
  });
  const [textPayload, setTextPayload] = useState('');
  const [jsonPayload, setJsonPayload] = useState('');
  const [versionPayload, setVersionPayload] = useState('');
  const [result, setResult] = useState<AssetPipelineRunResult | null>(null);
  const [submitResult, setSubmitResult] = useState<{ submitted: number; skipped: number } | null>(null);

  const loadOptions = useCallback(async () => {
    setLoadingOptions(true);
    try {
      const opts = await getAssetPipelineOptions(state.ontologyId);
      setOptions(opts);
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载选项失败');
    } finally {
      setLoadingOptions(false);
    }
  }, [state.ontologyId]);

  useEffect(() => {
    loadOptions();
  }, [loadOptions]);

  const structuredSourceTypes = useMemo(
    () => options?.source_types?.structured ?? [],
    [options],
  );
  const unstructuredSourceTypes = useMemo(
    () => options?.source_types?.unstructured ?? [],
    [options],
  );
  const indicatorSourceTypes = useMemo(
    () => options?.source_types?.indicator ?? [],
    [options],
  );
  const templates = useMemo(() => options?.templates ?? [], [options]);
  const ontologies = useMemo(() => options?.ontologies ?? [], [options]);

  const isStructured = useMemo(
    () => structuredSourceTypes.includes(state.sourceType ?? ''),
    [structuredSourceTypes, state.sourceType],
  );
  const isUnstructured = useMemo(
    () => unstructuredSourceTypes.includes(state.sourceType ?? ''),
    [unstructuredSourceTypes, state.sourceType],
  );
  const isIndicator = useMemo(
    () => indicatorSourceTypes.includes(state.sourceType ?? ''),
    [indicatorSourceTypes, state.sourceType],
  );

  const ontologyOptions = useMemo(
    () =>
      ontologies.map((o: AssetOntology) => ({
        value: String(o.ontology_id ?? o.id ?? ''),
        label: String(
          o.display_label
            ?? o.domain_display_name
            ?? o.display_name
            ?? o.name
            ?? o.ontology_id
            ?? o.id
            ?? '',
        ),
      })),
    [ontologies],
  );

  const templateOptions = useMemo(
    () =>
      templates.map((tpl: AssetTemplate) => ({
        value: String(tpl.template_path ?? tpl.name ?? ''),
        label: String(tpl.name ?? tpl.template_path ?? ''),
      })),
    [templates],
  );

  const handleOntologyChange = (val?: string) => {
    setState((s) => ({ ...s, ontologyId: val }));
  };

  const buildPayload = useCallback((): Record<string, unknown> => {
    if (isIndicator) {
      // BI 指标：ontology_id 走请求顶层字段，payload 只带可选 version_id
      return versionPayload ? { version_id: versionPayload } : {};
    }
    if (isUnstructured) {
      if (state.sourceType === 'natural_language') {
        return { text: textPayload, mode: 'schema_learning' };
      }
      return { text: textPayload, content: textPayload };
    }
    if (isStructured) {
      if (state.sourceType === 'json') {
        return { raw_json: jsonPayload };
      }
      if (state.sourceType === 'manual') {
        return { form_data: jsonPayload || textPayload };
      }
      if (state.sourceType === 'url') {
        return { url: textPayload };
      }
      if (state.sourceType === 'news' || state.sourceType === 'tavily') {
        return { query: textPayload };
      }
      return { text: textPayload, content: textPayload };
    }
    return {};
  }, [isIndicator, isUnstructured, isStructured, state.sourceType, textPayload, jsonPayload, versionPayload]);

  const handleRun = useCallback(async () => {
    if (!state.sourceType) {
      message.warning(t('请先选择数据源类型'));
      return;
    }
    setRunning(true);
    setResult(null);
    setSubmitResult(null);
    try {
      const res = await runAssetPipeline({
        source_type: state.sourceType,
        ontology_id: state.ontologyId,
        extraction_mode: state.extractionMode ?? 'exploratory',
        template_ref: isUnstructured ? state.templateRef : undefined,
        payload: buildPayload(),
        workspace_id: 'default',
      });
      if (res.status === 'error') {
        message.error(res.message ?? '执行失败');
        return;
      }
      setResult(res);
      setCurrent(3);
      message.success(t('抽取完成，共归集候选') + ` ${res.candidate_count} ` + t('条'));
    } catch (e) {
      message.error(e instanceof Error ? e.message : '执行失败');
    } finally {
      setRunning(false);
    }
  }, [state, isUnstructured, buildPayload, t]);

  const handleSubmit = useCallback(async () => {
    if (!result?.pipeline_run_id) return;
    setSubmitting(true);
    try {
      const res = await submitAssetPipeline(result.pipeline_run_id);
      if (res.status === 'error') {
        message.error('提交审核失败');
        return;
      }
      setSubmitResult({ submitted: res.submitted, skipped: res.skipped });
      message.success(t('已提交审核'));
    } catch (e) {
      message.error(e instanceof Error ? e.message : '提交审核失败');
    } finally {
      setSubmitting(false);
    }
  }, [result, t]);

  const steps = useMemo(
    () => [
      { title: t('选择本体'), icon: <ApartmentOutlined /> },
      { title: t('选择数据源'), icon: <DatabaseOutlined /> },
      { title: t('配置模板'), icon: <FileTextOutlined /> },
      { title: t('执行与审核'), icon: <CheckCircleOutlined /> },
    ],
    [t],
  );

  const candidateColumns = useMemo(
    () => [
      { title: t('术语'), dataIndex: 'canonical', key: 'canonical' },
      { title: t('语义类型'), dataIndex: 'semantic_type', key: 'semantic_type', width: 120 },
      { title: t('定义'), dataIndex: 'definition', key: 'definition', ellipsis: true },
      { title: t('置信度'), dataIndex: 'confidence', key: 'confidence', width: 90, render: (v: unknown) => (v != null ? Number(v).toFixed(2) : '-') },
    ],
    [t],
  );

  return (
    <SemanticAdminTabsContainer>
      <Space direction="vertical" style={{ width: '100%' }} size={16}>
        <Alert
          type="info"
          showIcon
          message={t('语义资产 Pipeline')}
          description={t('一条 Pipeline 完成结构化数据引入与非结构化文档抽取，产出候选语义资产并提交业务角色审核')}
        />
        <Steps current={current} items={steps} />

        {current === 0 && (
          <Card title={t('Step 0 · 选择本体（可选）')}>
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Paragraph type="secondary">
                {t('约束性抽取（constrained）要求本体已初始化且有类型定义；探索性抽取（exploratory）或使用预设模板可不依赖本体')}
              </Paragraph>
              <Form layout="vertical">
                <Form.Item label={t('目标本体')}>
                  <Select
                    allowClear
                    placeholder={t('选择本体（可选）')}
                    options={ontologyOptions}
                    value={state.ontologyId}
                    onChange={handleOntologyChange}
                    loading={loadingOptions}
                    style={{ maxWidth: 420 }}
                  />
                </Form.Item>
                <Form.Item label={t('抽取模式')}>
                  <Radio.Group
                    value={state.extractionMode}
                    onChange={(e) => setState((s) => ({ ...s, extractionMode: e.target.value }))}
                  >
                    <Radio.Button value="exploratory">{t('探索性（可推断新类型）')}</Radio.Button>
                    <Radio.Button value="constrained">{t('约束性（类型须已定义）')}</Radio.Button>
                  </Radio.Group>
                </Form.Item>
              </Form>
              <Button type="primary" onClick={() => setCurrent(1)}>
                {t('下一步')}
              </Button>
            </Space>
          </Card>
        )}

        {current === 1 && (
          <Card title={t('Step 1 · 选择数据源类型')}>
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Text strong>{t('结构化数据引入')}</Text>
              <Select
                style={{ maxWidth: 520 }}
                placeholder={t('选择结构化数据源')}
                value={isStructured ? state.sourceType : undefined}
                onChange={(v) => setState((s) => ({ ...s, sourceType: v }))}
                options={structuredSourceTypes.map((s) => ({ value: s, label: s }))}
              />
              <Text strong>{t('非结构化文档抽取')}</Text>
              <Select
                style={{ maxWidth: 520 }}
                placeholder={t('选择非结构化数据源')}
                value={isUnstructured ? state.sourceType : undefined}
                onChange={(v) => setState((s) => ({ ...s, sourceType: v }))}
                options={unstructuredSourceTypes.map((s) => ({ value: s, label: s }))}
              />
              <Text strong>{t('BI 业务指标抽取')}</Text>
              <Paragraph type="secondary">
                {t('业务指标抽取需先在 Step 0 选择目标本体；指标将归集为「属性」候选')}
              </Paragraph>
              <Select
                style={{ maxWidth: 520 }}
                placeholder={t('选择业务指标数据源')}
                value={isIndicator ? state.sourceType : undefined}
                onChange={(v) => setState((s) => ({ ...s, sourceType: v }))}
                options={indicatorSourceTypes.map((s) => ({ value: s, label: s }))}
              />
              <Space>
                <Button onClick={() => setCurrent(0)}>{t('上一步')}</Button>
                <Button type="primary" onClick={() => setCurrent(2)} disabled={!state.sourceType}>
                  {t('下一步')}
                </Button>
              </Space>
            </Space>
          </Card>
        )}

        {current === 2 && (
          <Card title={t('Step 2 · 配置模板与内容')}>
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              {isUnstructured && (
                <Form layout="vertical">
                  <Form.Item label={t('抽取模板')}>
                    <Select
                      allowClear
                      style={{ maxWidth: 520 }}
                      placeholder={t('选择模板（留空使用预设默认）')}
                      options={templateOptions}
                      value={state.templateRef}
                      onChange={(v) => setState((s) => ({ ...s, templateRef: v }))}
                    />
                  </Form.Item>
                </Form>
              )}
              {isUnstructured && (
                <Form layout="vertical">
                  <Form.Item label={t('文本内容')}>
                    <Input.TextArea
                      rows={6}
                      value={textPayload}
                      onChange={(e) => setTextPayload(e.target.value)}
                      placeholder={t('粘贴待抽取的文本或文档内容')}
                    />
                  </Form.Item>
                </Form>
              )}
              {isStructured && state.sourceType === 'json' && (
                <Form layout="vertical">
                  <Form.Item label={t('JSON 数据')}>
                    <Input.TextArea
                      rows={6}
                      value={jsonPayload}
                      onChange={(e) => setJsonPayload(e.target.value)}
                      placeholder='{"name": "..."}'
                    />
                  </Form.Item>
                </Form>
              )}
              {isStructured && state.sourceType !== 'json' && (
                <Form layout="vertical">
                  <Form.Item label={t('内容 / 参数')}>
                    <Input.TextArea
                      rows={4}
                      value={textPayload}
                      onChange={(e) => setTextPayload(e.target.value)}
                      placeholder={t('URL、查询词或表单内容')}
                    />
                  </Form.Item>
                </Form>
              )}
              {isIndicator && (
                <Form layout="vertical">
                  <Form.Item label={t('本体版本（可选）')}>
                    <Input
                      style={{ maxWidth: 520 }}
                      value={versionPayload}
                      onChange={(e) => setVersionPayload(e.target.value)}
                      placeholder={t('留空则抽取该本体全部版本的指标')}
                    />
                  </Form.Item>
                </Form>
              )}
              <Space>
                <Button onClick={() => setCurrent(1)}>{t('上一步')}</Button>
                <Button
                  type="primary"
                  icon={<CloudUploadOutlined />}
                  loading={running}
                  onClick={handleRun}
                >
                  {t('执行抽取')}
                </Button>
              </Space>
            </Space>
          </Card>
        )}

        {current === 3 && (
          <Card title={t('Step 3 · 结果与提交审核')}>
            <Space direction="vertical" style={{ width: '100%' }} size={16}>
              {result && (
                <>
                  <Row gutter={16}>
                    <Col span={8}>
                      <Card size="small">
                        <Text type="secondary">{t('候选数量')}</Text>
                        <Title level={3} style={{ margin: 0 }}>{result.candidate_count}</Title>
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small">
                        <Text type="secondary">{t('来源类型')}</Text>
                        <div>
                          <Tag color={result.source_kind === 'structured' ? 'blue' : 'green'}>
                            {result.source_kind === 'structured' ? t('结构化') : t('非结构化')}
                          </Tag>
                        </div>
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small">
                        <Text type="secondary">{t('审核状态')}</Text>
                        <div>
                          {submitResult ? (
                            <Tag color="green">
                              {t('已提交')} {submitResult.submitted}{t('条')}
                            </Tag>
                          ) : (
                            <Tag color="orange">{t('待提交')}</Tag>
                          )}
                        </div>
                      </Card>
                    </Col>
                  </Row>
                  <Table<AssetCandidate>
                    rowKey={(r) => String(r.id ?? r.canonical)}
                    dataSource={result.candidates}
                    columns={candidateColumns}
                    size="small"
                    pagination={{ pageSize: 10 }}
                  />
                  <Space>
                    <Button onClick={() => setCurrent(2)}>{t('返回修改')}</Button>
                    <Button
                      type="primary"
                      icon={<SendOutlined />}
                      loading={submitting}
                      onClick={handleSubmit}
                      disabled={!!submitResult}
                    >
                      {t('提交审核')}
                    </Button>
                  </Space>
                </>
              )}
              {!result && <Alert type="warning" message={t('暂无执行结果')} />}
            </Space>
          </Card>
        )}
      </Space>
    </SemanticAdminTabsContainer>
  );
}
