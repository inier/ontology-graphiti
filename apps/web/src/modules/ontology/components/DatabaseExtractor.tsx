/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useCallback } from 'react';
import {
  Card, Input, InputNumber, Select, Button, Switch,
  Space, Alert, Spin, Steps, message, Tag,
} from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import {
  DatabaseOutlined, ApiOutlined, ThunderboltOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { ontologyApi } from '../services/ontologyApi';
import { ExtractionPreview } from './ExtractionPreview';
import type { ExtractionResult, ExtractionConflict } from './ExtractionPreview';
import { useI18n } from '@/modules/shared/hooks/useI18n';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface DatabaseExtractorProps {
  ontologyId: string;
  onImportComplete?: () => void;
}

type DbType = 'mysql' | 'postgresql' | 'sqlite';
type StepStatus = 'wait' | 'process' | 'finish' | 'error';

interface ConnectionFormValues {
  db_type: DbType;
  host?: string;
  port?: number;
  database: string;
  username?: string;
  password?: string;
}

/* ------------------------------------------------------------------ */
/*  Default port map                                                   */
/* ------------------------------------------------------------------ */

const DEFAULT_PORTS: Record<DbType, number | null> = {
  mysql: 3306,
  postgresql: 5432,
  sqlite: null,
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function DatabaseExtractor({ ontologyId, onImportComplete }: DatabaseExtractorProps) {
  const { t } = useI18n('ontology');
  const [form] = Form.useForm<ConnectionFormValues>();

  // ── State ────────────────────────────────────────────────────────
  const [currentStep, setCurrentStep] = useState(0);
  const [testing, setTesting] = useState(false);
  const [connectionOk, setConnectionOk] = useState(false);
  const [availableTables, setAvailableTables] = useState<string[]>([]);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [useLLM, setUseLLM] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractionResult, setExtractionResult] = useState<ExtractionResult | null>(null);
  const [extractionConflicts, setExtractionConflicts] = useState<ExtractionConflict[]>([]);
  const [sessionId, setSessionId] = useState<string>('');
  const [dbType, setDbType] = useState<DbType>('mysql');

  // ── Step 1: Test Connection ───────────────────────────────────────
  const handleTestConnection = useCallback(async () => {
    try {
      const values = await form.validateFields();
      setTesting(true);
      setConnectionOk(false);

      const payload: Record<string, unknown> = {
        db_type: values.db_type,
        database: values.database,
      };
      if (values.db_type !== 'sqlite') {
        payload.host = values.host;
        payload.port = values.port;
        payload.username = values.username;
        payload.password = values.password;
      }

      const result = await ontologyApi.extraction.testConnection(payload) as any;

      if (result?.status === 'ok' || result?.tables) {
        setConnectionOk(true);
        const tables: string[] = result.tables || [];
        setAvailableTables(tables);
        setSelectedTables(tables);
        setCurrentStep(1);
        message.success(t('数据库连接成功'));
      } else {
        message.error(result?.message || t('databaseExtract.connectFailed', { msg: '' }));
      }
    } catch (e) {
      if ((e as any)?.errorFields) return; // form validation
      message.error(t('databaseExtract.connectFailed', { msg: (e as Error).message }));
    } finally {
      setTesting(false);
    }
  }, [form, t]);

  // ── Step 2: Start Extraction ──────────────────────────────────────
  const handleExtract = useCallback(async () => {
    if (selectedTables.length === 0) {
      message.warning(t('请先选择至少一张数据表'));
      return;
    }

    setExtracting(true);
    try {
      const formValues = form.getFieldsValue();
      const payload: Record<string, unknown> = {
        ontology_id: ontologyId,
        db_type: formValues.db_type,
        database: formValues.database,
        table_filter: selectedTables,
        use_llm_enrichment: useLLM,
      };
      if (formValues.db_type !== 'sqlite') {
        payload.host = formValues.host;
        payload.port = formValues.port;
        payload.username = formValues.username;
        payload.password = formValues.password;
      }

      const result = await ontologyApi.extraction.extractDatabase(payload) as any;

      setSessionId(result?.session_id || '');
      setExtractionResult({
        object_types: result?.result?.object_types || result?.object_types || [],
        link_types: result?.result?.link_types || result?.link_types || [],
        action_types: result?.result?.action_types || result?.action_types || [],
        rule_types: result?.result?.rule_types || result?.rule_types || [],
      });
      setExtractionConflicts(result?.conflicts || []);
      setCurrentStep(2);
      message.success(t('提取成功'));
    } catch (e) {
      message.error(t('databaseExtract.extractFailed', { msg: (e as Error).message }));
    } finally {
      setExtracting(false);
    }
  }, [form, ontologyId, selectedTables, useLLM, t]);

  // ── Step indicators ───────────────────────────────────────────────
  const stepStatuses: StepStatus[] = [
    connectionOk ? 'finish' : currentStep === 0 ? 'process' : 'wait',
    extractionResult ? 'finish' : currentStep === 1 ? 'process' : 'wait',
    currentStep === 2 ? 'process' : 'wait',
  ];

  const isSqlite = dbType === 'sqlite';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── Steps indicator ──────────────────────────────────────── */}
      <Steps
        size="small"
        current={currentStep}
        items={[
          { title: t('连接数据库'), status: stepStatuses[0], icon: connectionOk ? <CheckCircleOutlined /> : <DatabaseOutlined /> },
          { title: t('选择表'), status: stepStatuses[1], icon: <ApiOutlined /> },
          { title: t('预览结果'), status: stepStatuses[2], icon: <ThunderboltOutlined /> },
        ]}
      />

      {/* ── Step 0: Connection Form ──────────────────────────────── */}
      {currentStep === 0 && (
        <Card title={t('数据库连接配置')} size="small">
          <Form
            form={form}
            layout="vertical"
            initialValues={{ db_type: 'mysql', port: 3306 }}
          >
            <Form.Item name="db_type" label={t('数据库类型')} rules={[{ required: true, message: t('请选择数据库类型') }]}>
              <Select
                options={[
                  { label: t('MySQL'), value: 'mysql' },
                  { label: t('PostgreSQL'), value: 'postgresql' },
                  { label: t('SQLite'), value: 'sqlite' },
                ]}
                onChange={(v: DbType) => {
                  setDbType(v);
                  const port = DEFAULT_PORTS[v];
                  if (port) form.setFieldsValue({ port });
                  else form.setFieldsValue({ port: undefined });
                }}
              />
            </Form.Item>

            {!isSqlite && (
              <>
                <Form.Item name="host" label={t('主机')} rules={[{ required: true, message: t('请输入主机地址') }]}>
                  <Input placeholder={t('请输入数据库主机地址')} />
                </Form.Item>
                <Form.Item name="port" label={t('端口')} rules={[{ required: true, message: t('请输入端口号') }]}>
                  <InputNumber style={{ width: '100%' }} min={1} max={65535} />
                </Form.Item>
                <Form.Item name="username" label={t('用户名')} rules={[{ required: true, message: t('请输入用户名') }]}>
                  <Input />
                </Form.Item>
                <Form.Item name="password" label={t('密码')}>
                  <Input.Password />
                </Form.Item>
              </>
            )}

            <Form.Item
              name="database"
              label={isSqlite ? t('数据库文件') : t('数据库名称')}
              rules={[{ required: true, message: isSqlite ? t('请选择数据库文件') : t('请输入数据库名称') }]}
            >
              <Input placeholder={isSqlite ? t('请输入 SQLite 数据库文件路径') : t('请输入数据库名称')} />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button
                  type="primary"
                  icon={<ApiOutlined />}
                  onClick={handleTestConnection}
                  loading={testing}
                >
                  {t('测试连接')}
                </Button>
                {connectionOk && (
                  <Tag icon={<CheckCircleOutlined />} color="success">{t('连接成功')}</Tag>
                )}
              </Space>
            </Form.Item>
          </Form>
        </Card>
      )}

      {/* ── Step 1: Table Filter ─────────────────────────────────── */}
      {currentStep === 1 && (
        <Card
          title={t('选择数据表')}
          size="small"
          extra={
            <Button size="small" onClick={() => { setCurrentStep(0); setConnectionOk(false); }}>
              {t('返回配置')}
            </Button>
          }
        >
          <Space orientation="vertical" style={{ width: '100%' }} size="middle">
            <Alert
              type="info"
              title={t('databaseExtract.tablesFound', { count: availableTables.length })}
              showIcon
            />

            <Form layout="vertical">
              <Form.Item label={t('选择要提取的表')}>
                <Select
                  mode="multiple"
                  placeholder={t('请选择数据表')}
                  value={selectedTables}
                  onChange={setSelectedTables}
                  options={availableTables.map((t) => ({ label: t, value: t }))}
                  style={{ width: '100%' }}
                  maxTagCount="responsive"
                />
              </Form.Item>

              <Form.Item label={t('LLM 增强')}>
                <Space>
                  <Switch checked={useLLM} onChange={setUseLLM} />
                  <span style={{ color: '#666' }}>{t('使用 LLM 丰富本体定义（推荐）')}</span>
                </Space>
              </Form.Item>
            </Form>

            <div style={{ textAlign: 'right' }}>
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={handleExtract}
                loading={extracting}
                disabled={selectedTables.length === 0}
                size="large"
              >
                {t('开始提取')}
              </Button>
            </div>
          </Space>
        </Card>
      )}

      {/* ── Step 2: Extraction Preview ───────────────────────────── */}
      {currentStep === 2 && extractionResult && (
        <>
          <Card
            title={t('提取结果预览')}
            size="small"
            extra={
              <Space>
                <Button size="small" onClick={() => { setCurrentStep(1); setExtractionResult(null); }}>
                  {t('重新选择表')}
                </Button>
                <Button size="small" onClick={() => { setCurrentStep(0); setConnectionOk(false); setExtractionResult(null); }}>
                  {t('重新连接')}
                </Button>
              </Space>
            }
          />
          <ExtractionPreview
            sessionId={sessionId}
            result={extractionResult}
            conflicts={extractionConflicts}
            ontologyId={ontologyId}
            onImportComplete={onImportComplete}
          />
        </>
      )}

      {/* ── Loading overlay ──────────────────────────────────────── */}
      {extracting && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" description={t('正在提取数据库...')} />
        </div>
      )}
    </div>
  );
}

export default DatabaseExtractor;
