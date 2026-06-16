/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useCallback } from 'react';
import {
  Card, Input, Switch, Button, Space, Alert, Spin, Steps, message,
} from 'antd';
import {
  MessageOutlined, ThunderboltOutlined, CheckCircleOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { ontologyApi } from '../services/ontologyApi';
import { ExtractionPreview } from './ExtractionPreview';
import type { ExtractionResult, ExtractionConflict } from './ExtractionPreview';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface NLExtractorProps {
  ontologyId: string;
  onImportComplete?: () => void;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function NLExtractor({ ontologyId, onImportComplete }: NLExtractorProps) {
  // ── State ────────────────────────────────────────────────────────
  const [text, setText] = useState('');
  const [autoSearch, setAutoSearch] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [extractionResult, setExtractionResult] = useState<ExtractionResult | null>(null);
  const [extractionConflicts, setExtractionConflicts] = useState<ExtractionConflict[]>([]);
  const [sessionId, setSessionId] = useState<string>('');

  // ── Start Extraction ──────────────────────────────────────────────
  const handleExtract = useCallback(async () => {
    if (!text.trim()) {
      message.warning('请输入自然语言描述');
      return;
    }

    setExtracting(true);
    try {
      const payload: Record<string, unknown> = {
        ontology_id: ontologyId,
        text: text.trim(),
        auto_search: autoSearch,
      };

      const result = await ontologyApi.extraction.extractNL(payload) as any;

      setSessionId(result?.session_id || '');
      setExtractionResult({
        object_types: result?.result?.object_types || result?.object_types || [],
        link_types: result?.result?.link_types || result?.link_types || [],
        action_types: result?.result?.action_types || result?.action_types || [],
        rule_types: result?.result?.rule_types || result?.rule_types || [],
      });
      setExtractionConflicts(result?.conflicts || []);
      setCurrentStep(1);
      message.success('提取完成');
    } catch (e) {
      message.error(`提取失败: ${(e as Error).message}`);
    } finally {
      setExtracting(false);
    }
  }, [text, autoSearch, ontologyId]);

  // ── Reset ─────────────────────────────────────────────────────────
  const handleReset = useCallback(() => {
    setCurrentStep(0);
    setExtractionResult(null);
    setExtractionConflicts([]);
    setSessionId('');
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── Steps indicator ──────────────────────────────────────── */}
      <Steps
        size="small"
        current={currentStep}
        items={[
          { title: '输入描述', status: currentStep === 0 ? 'process' : 'finish', icon: currentStep > 0 ? <CheckCircleOutlined /> : <MessageOutlined /> },
          { title: '预览导入', status: currentStep === 1 ? 'process' : 'wait', icon: <ThunderboltOutlined /> },
        ]}
      />

      {/* ── Step 0: Text Input ───────────────────────────────────── */}
      {currentStep === 0 && (
        <Card title="自然语言提取" size="small">
          <Space orientation="vertical" style={{ width: '100%' }} size="middle">
            <Alert
              type="info"
              message="请用自然语言描述您的业务领域，系统将自动提取对象类型、关系类型、动作类型和规则"
              showIcon
            />

            <Input.TextArea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="例如：我们的系统管理客户和订单。每个客户可以下多个订单，每个订单包含多个商品。订单有状态（待付款、已付款、已发货、已完成），当订单状态变更时需要通知客户。客户有姓名、邮箱、手机号等属性..."
              autoSize={{ minRows: 3, maxRows: 10 }}
            />

            <Space>
              <Switch
                checked={autoSearch}
                onChange={setAutoSearch}
                checkedChildren="开"
                unCheckedChildren="关"
              />
              <span style={{ color: '#666' }}>
                <SearchOutlined /> 联网检索补充领域知识
              </span>
            </Space>

            <div style={{ textAlign: 'right' }}>
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={handleExtract}
                loading={extracting}
                disabled={!text.trim()}
                size="large"
              >
                开始提取
              </Button>
            </div>
          </Space>
        </Card>
      )}

      {/* ── Step 1: Extraction Preview ───────────────────────────── */}
      {currentStep === 1 && extractionResult && (
        <>
          <Card
            title="提取结果预览"
            size="small"
            extra={
              <Button size="small" onClick={handleReset}>
                重新提取
              </Button>
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
          <Spin size="large" description="正在分析自然语言描述..." />
        </div>
      )}
    </div>
  );
}

export default NLExtractor;
