import { useState, useEffect, useCallback } from 'react';
import { Tabs, Spin, Empty, Tag } from 'antd';
import { ExperimentOutlined, DatabaseOutlined } from '@ant-design/icons';
import { IngestPanel } from '../../ingest';
import { api } from '../../shared';

interface ExtractionStep {
  title: string;
  input: string;
  output: string;
  color: string;
}

const PIPELINE_REFERENCE: ExtractionStep[] = [
  { title: '文档预处理', input: '原始文档', output: '结构化文本段落', color: '#1890ff' },
  { title: '实体识别与抽取', input: '结构化文本', output: '实体列表及属性', color: '#52c41a' },
  { title: '关系构建', input: '实体列表', output: '实体关系三元组', color: '#722ed1' },
  { title: '知识入库', input: '实体关系三元组', output: '知识图谱更新', color: '#fa8c16' },
];

interface ExtractionRecord {
  id: string;
  stage: string;
  operation: string;
  status: string;
  timestamp: string;
  details: Record<string, any>;
}

export function SmartGeneration() {
  const tabItems = [
    {
      key: 'ingest',
      label: (
        <span>
          <DatabaseOutlined style={{ marginRight: 4 }} />
          数据摄入
        </span>
      ),
      children: <IngestPanel />,
    },
    {
      key: 'extraction',
      label: (
        <span>
          <ExperimentOutlined style={{ marginRight: 4 }} />
          抽取记录
        </span>
      ),
      children: <ExtractionRecords />,
    },
  ];

  return (
    <Tabs
      defaultActiveKey="ingest"
      items={tabItems}
    />
  );
}

function ExtractionRecords({ ingestId }: { ingestId?: string }) {
  const [records, setRecords] = useState<ExtractionRecord[]>([]);
  const [loading, setLoading] = useState(false);

  const loadRecords = useCallback(async () => {
    if (!ingestId) return;
    setLoading(true);
    try {
      const data = await api.getFullIngestRecord(ingestId);
      setRecords(
        (data.logs || []).map((log) => ({
          id: log.id,
          stage: log.stage,
          operation: log.operation,
          status: log.status,
          timestamp: log.timestamp,
          details: log.details as Record<string, any>,
        }))
      );
    } catch {
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }, [ingestId]);

  useEffect(() => {
    loadRecords();
  }, [loadRecords]);

  const STAGE_COLORS: Record<string, string> = {
    collection: '#1890ff',
    cleaning: '#13c2c2',
    llm: '#52c41a',
    ontology: '#fa8c16',
    version: '#722ed1',
    graph: '#f5222d',
  };

  const renderStep = (step: ExtractionStep, index: number, isReal?: boolean) => (
    <div
      key={index}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '12px 16px',
        background: '#fafafa',
        borderRadius: 8,
        borderLeft: `3px solid ${step.color}`,
      }}
    >
      <div style={{ width: 28, height: 28, borderRadius: '50%', background: step.color, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, marginRight: 16, flexShrink: 0 }}>
        {index + 1}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>
          {step.title}
          {isReal && <Tag color="blue" style={{ marginLeft: 8 }}>实际数据</Tag>}
        </div>
        <div style={{ fontSize: 12, color: '#8c8c8c' }}>
          输入：{step.input} → 输出：{step.output}
        </div>
      </div>
    </div>
  );

  return (
    <div style={{ padding: '16px 0' }}>
      {loading && <Spin style={{ display: 'block', margin: '40px auto' }} />}

      {ingestId && records.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ marginBottom: 12, fontWeight: 600, fontSize: 14 }}>抽取记录（摄入 {ingestId}）</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {records.map((rec, index) => {
              const details = rec.details || {};
              const inputStr = details.input ? JSON.stringify(details.input) : rec.stage;
              const outputStr = details.output ? JSON.stringify(details.output) : rec.operation;
              return renderStep(
                {
                  title: rec.operation || rec.stage,
                  input: inputStr.length > 60 ? inputStr.substring(0, 60) + '...' : inputStr,
                  output: outputStr.length > 60 ? outputStr.substring(0, 60) + '...' : outputStr,
                  color: STAGE_COLORS[rec.stage] || '#8c8c8c',
                },
                index,
                true
              );
            })}
          </div>
        </div>
      )}

      {ingestId && !loading && records.length === 0 && (
        <Empty description="暂无抽取记录" style={{ margin: '40px 0' }} />
      )}

      <div style={{ marginBottom: 16, color: '#8c8c8c', fontSize: 13 }}>
        流程说明：展示当前本体版本定义的自动抽取过程，以及每一步的输入和输出。
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {PIPELINE_REFERENCE.map((step, index) => renderStep(step, index))}
      </div>
    </div>
  );
}
