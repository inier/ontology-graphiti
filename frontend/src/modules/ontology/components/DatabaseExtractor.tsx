/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useCallback } from 'react';
import {
  Card, Form, Input, InputNumber, Select, Button, Switch,
  Space, Alert, Spin, Steps, message, Tag,
} from 'antd';
import {
  DatabaseOutlined, ApiOutlined, ThunderboltOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { ontologyApi } from '../services/ontologyApi';
import { ExtractionPreview } from './ExtractionPreview';
import type { ExtractionResult, ExtractionConflict } from './ExtractionPreview';

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
        message.success('连接成功');
      } else {
        message.error(result?.message || '连接失败');
      }
    } catch (e) {
      if ((e as any)?.errorFields) return; // form validation
      message.error(`连接失败: ${(e as Error).message}`);
    } finally {
      setTesting(false);
    }
  }, [form]);

  // ── Step 2: Start Extraction ──────────────────────────────────────
  const handleExtract = useCallback(async () => {
    if (selectedTables.length === 0) {
      message.warning('请至少选择一个表');
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
      message.success('抽取完成');
    } catch (e) {
      message.error(`抽取失败: ${(e as Error).message}`);
    } finally {
      setExtracting(false);
    }
  }, [form, ontologyId, selectedTables, useLLM]);

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
          { title: '连接数据库', status: stepStatuses[0], icon: connectionOk ? <CheckCircleOutlined /> : <DatabaseOutlined /> },
          { title: '选择表', status: stepStatuses[1], icon: <ApiOutlined /> },
          { title: '预览导入', status: stepStatuses[2], icon: <ThunderboltOutlined /> },
        ]}
      />

      {/* ── Step 0: Connection Form ──────────────────────────────── */}
      {currentStep === 0 && (
        <Card title="数据库连接配置" size="small">
          <Form
            form={form}
            layout="vertical"
            initialValues={{ db_type: 'mysql', port: 3306 }}
          >
            <Form.Item name="db_type" label="数据库类型" rules={[{ required: true, message: '请选择数据库类型' }]}>
              <Select
                options={[
                  { label: 'MySQL', value: 'mysql' },
                  { label: 'PostgreSQL', value: 'postgresql' },
                  { label: 'SQLite', value: 'sqlite' },
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
                <Form.Item name="host" label="主机地址" rules={[{ required: true, message: '请输入主机地址' }]}>
                  <Input placeholder="例如: 192.168.1.100" />
                </Form.Item>
                <Form.Item name="port" label="端口" rules={[{ required: true, message: '请输入端口' }]}>
                  <InputNumber style={{ width: '100%' }} min={1} max={65535} />
                </Form.Item>
                <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
                  <Input />
                </Form.Item>
                <Form.Item name="password" label="密码">
                  <Input.Password />
                </Form.Item>
              </>
            )}

            <Form.Item
              name="database"
              label={isSqlite ? '数据库文件路径' : '数据库名称'}
              rules={[{ required: true, message: isSqlite ? '请输入文件路径' : '请输入数据库名称' }]}
            >
              <Input placeholder={isSqlite ? '/path/to/database.db' : 'my_database'} />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button
                  type="primary"
                  icon={<ApiOutlined />}
                  onClick={handleTestConnection}
                  loading={testing}
                >
                  测试连接
                </Button>
                {connectionOk && (
                  <Tag icon={<CheckCircleOutlined />} color="success">连接成功</Tag>
                )}
              </Space>
            </Form.Item>
          </Form>
        </Card>
      )}

      {/* ── Step 1: Table Filter ─────────────────────────────────── */}
      {currentStep === 1 && (
        <Card
          title="选择要抽取的表"
          size="small"
          extra={
            <Button size="small" onClick={() => { setCurrentStep(0); setConnectionOk(false); }}>
              返回修改连接
            </Button>
          }
        >
          <Space orientation="vertical" style={{ width: '100%' }} size="middle">
            <Alert
              type="info"
              message={`已发现 ${availableTables.length} 个表，请选择需要抽取的表`}
              showIcon
            />

            <Form layout="vertical">
              <Form.Item label="选择表">
                <Select
                  mode="multiple"
                  placeholder="选择要抽取的表"
                  value={selectedTables}
                  onChange={setSelectedTables}
                  options={availableTables.map((t) => ({ label: t, value: t }))}
                  style={{ width: '100%' }}
                  maxTagCount="responsive"
                />
              </Form.Item>

              <Form.Item label="LLM 增强">
                <Space>
                  <Switch checked={useLLM} onChange={setUseLLM} />
                  <span style={{ color: '#666' }}>使用 LLM 补充字段描述和关系推断</span>
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
                开始抽取
              </Button>
            </div>
          </Space>
        </Card>
      )}

      {/* ── Step 2: Extraction Preview ───────────────────────────── */}
      {currentStep === 2 && extractionResult && (
        <>
          <Card
            title="抽取结果预览"
            size="small"
            extra={
              <Space>
                <Button size="small" onClick={() => { setCurrentStep(1); setExtractionResult(null); }}>
                  返回重新选择
                </Button>
                <Button size="small" onClick={() => { setCurrentStep(0); setConnectionOk(false); setExtractionResult(null); }}>
                  重新连接
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
          <Spin size="large" description="正在抽取数据库 Schema..." />
        </div>
      )}
    </div>
  );
}

export default DatabaseExtractor;
