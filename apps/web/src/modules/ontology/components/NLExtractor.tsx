/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useCallback, useEffect } from 'react';
import {
  Card, Input, Switch, Button, Space, Alert, Spin, Steps, Tabs, Select, message, Progress,
} from 'antd';
import {
  MessageOutlined, ThunderboltOutlined, CheckCircleOutlined,
  SearchOutlined, FileTextOutlined, DatabaseOutlined,
} from '@ant-design/icons';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { ontologyApi } from '../services/ontologyApi';
import { ExtractionPreview } from './ExtractionPreview';
import { DocumentUploader } from './DocumentUploader';
import { KnowledgeBaseSelector } from './KnowledgeBaseSelector';
import { useExtractionProgress } from '../hooks/useExtractionProgress';
import type { ExtractionResult, ExtractionConflict } from './ExtractionPreview';

export interface NLExtractorProps {
  ontologyId: string;
  onImportComplete?: () => void;
}

export function NLExtractor({ ontologyId, onImportComplete }: NLExtractorProps) {
  const { t } = useI18n('ontology');

  const METHOD_OPTIONS = [
    { value: 'auto', label: t('自动选择') },
    { value: 'graph_rag', label: 'Graph RAG' },
    { value: 'light_rag', label: 'Light RAG' },
  ];
  const [activeTab, setActiveTab] = useState('text');
  const [text, setText] = useState('');
  const [autoSearch, setAutoSearch] = useState(false);
  const [selectedMethod, setSelectedMethod] = useState<string>('auto');
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [extracting, setExtracting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [extractionResult, setExtractionResult] = useState<ExtractionResult | null>(null);
  const [extractionConflicts, setExtractionConflicts] = useState<ExtractionConflict[]>([]);
  const [sessionId, setSessionId] = useState<string>('');

  const { progress } = useExtractionProgress(sessionId || null);

  const handleExtract = useCallback(async () => {
    if (!text.trim()) {
      message.warning(t('请输入自然语言描述'));
      return;
    }

    setExtracting(true);
    setExtractionResult(null);
    setExtractionConflicts([]);
    setSessionId('');

    try {
      const payload: Record<string, unknown> = {
        ontology_id: ontologyId,
        text: text.trim(),
        auto_search: autoSearch,
        source_type: 'text',
        method: selectedMethod !== 'auto' ? selectedMethod : undefined,
        template_id: selectedTemplate || undefined,
      };

      const result = await ontologyApi.extraction.extractNL(payload) as any;
      const newSessionId = result?.session_id || '';
      setSessionId(newSessionId);

      setExtractionResult({
        object_types: result?.result?.object_types || result?.object_types || [],
        link_types: result?.result?.link_types || result?.link_types || [],
        action_types: result?.result?.action_types || result?.action_types || [],
        rule_types: result?.result?.rule_types || result?.rule_types || [],
        process_types: result?.result?.process_types || [],
        function_types: result?.result?.function_types || [],
        indicator_types: result?.result?.indicator_types || [],
      });
      setExtractionConflicts(result?.conflicts || []);
      setCurrentStep(1);
      message.success(t('提取完成'));
    } catch (e) {
      message.error(t('extraction.extractFailed', { msg: (e as Error).message }));
    } finally {
      setExtracting(false);
    }
  }, [text, autoSearch, ontologyId, selectedMethod, selectedTemplate]);

  const handleExtractionComplete = useCallback((result: any) => {
    setSessionId(result?.session_id || '');
    setExtractionResult({
      object_types: result?.result?.object_types || result?.object_types || [],
      link_types: result?.result?.link_types || result?.link_types || [],
      action_types: result?.result?.action_types || result?.action_types || [],
      rule_types: result?.result?.rule_types || result?.rule_types || [],
      process_types: result?.result?.process_types || [],
      function_types: result?.result?.function_types || [],
      indicator_types: result?.result?.indicator_types || [],
    });
    setExtractionConflicts(result?.conflicts || []);
    setCurrentStep(1);
  }, []);

  const handleReset = useCallback(() => {
    setCurrentStep(0);
    setExtractionResult(null);
    setExtractionConflicts([]);
    setSessionId('');
  }, []);

  const handleReextract = useCallback(() => {
    // Reset result then re-trigger extraction with same text/method/template
    setExtractionResult(null);
    setExtractionConflicts([]);
    setSessionId('');
    setCurrentStep(0);
    // Trigger handleExtract on next tick after state reset
    setTimeout(() => {
      void handleExtract();
    }, 50);
  }, [handleExtract]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Steps
        size="small"
        current={currentStep}
        items={[
          { title: t('输入描述'), status: currentStep === 0 ? 'process' : 'finish', icon: currentStep > 0 ? <CheckCircleOutlined /> : <MessageOutlined /> },
          { title: t('预览导入'), status: currentStep === 1 ? 'process' : 'wait', icon: <ThunderboltOutlined /> },
        ]}
      />

      {currentStep === 0 && (
        <Card title={t('知识提取')} size="small">
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                key: 'text',
                label: (
                  <span>
                    <MessageOutlined /> {t('文本输入')}
                  </span>
                ),
                children: (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <Alert
                      type="info"
                      title={t('请用自然语言描述您的业务领域，系统将使用 Hyper-Extract 模板化提取对象类型、关系类型等')}
                      showIcon
                    />

                    <Input.TextArea
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      placeholder={t('例如：我们的系统管理客户和订单。每个客户可以下多个订单，每个订单包含多个商品...')}
                      autoSize={{ minRows: 3, maxRows: 10 }}
                    />

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                      <Space wrap>
                        <Space>
                          <Switch
                            checked={autoSearch}
                            onChange={setAutoSearch}
                            checkedChildren={t('开')}
                            unCheckedChildren={t('关')}
                          />
                          <span style={{ color: '#666' }}>
                            <SearchOutlined /> {t('联网检索补充')}
                          </span>
                        </Space>
                        <Select
                          value={selectedMethod}
                          onChange={setSelectedMethod}
                          options={METHOD_OPTIONS}
                          style={{ width: 140 }}
                          size="small"
                        />
                        <Select
                          value={selectedTemplate || undefined}
                          onChange={setSelectedTemplate}
                          placeholder={t('自动选择模板')}
                          allowClear
                          style={{ width: 180 }}
                          size="small"
                          options={[
                            { value: '', label: t('自动选择模板') },
                            { value: 'general/base_graph', label: t('通用知识图谱') },
                            { value: 'general/concept_graph', label: t('概念关系图') },
                            { value: 'finance/earnings_summary', label: t('财报摘要') },
                            { value: 'legal/contract_obligation', label: t('合同义务') },
                          ]}
                        />
                      </Space>
                      <Button
                        type="primary"
                        icon={<ThunderboltOutlined />}
                        onClick={handleExtract}
                        loading={extracting}
                        disabled={!text.trim()}
                        size="large"
                      >
                        {t('开始提取')}
                      </Button>
                    </div>
                  </div>
                ),
              },
              {
                key: 'document',
                label: (
                  <span>
                    <FileTextOutlined /> {t('文档上传')}
                  </span>
                ),
                children: (
                  <DocumentUploader
                    ontologyId={ontologyId}
                    onExtractionComplete={handleExtractionComplete}
                  />
                ),
              },
              {
                key: 'knowledge_base',
                label: (
                  <span>
                    <DatabaseOutlined /> {t('知识库选择')}
                  </span>
                ),
                children: (
                  <KnowledgeBaseSelector
                    ontologyId={ontologyId}
                    onExtractionComplete={handleExtractionComplete}
                  />
                ),
              },
            ]}
          />
        </Card>
      )}

      {currentStep === 1 && extractionResult && (
        <>
          <Card
            title={t('提取结果预览')}
            size="small"
            extra={
              <Button size="small" onClick={handleReextract}>
                {t('重新提取')}
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

      {extracting && (
        <Card title={t('提取进度')} size="small">
          <div style={{ padding: 24 }}>
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <Spin size="large" />
            </div>
            <Progress
              percent={progress?.progress_percent || 0}
              showInfo={true}
              strokeColor={{
                '0%': '#10B981',
                '100%': '#3B82F6',
              }}
              size="default"
            />
            <div style={{ textAlign: 'center', marginTop: 12, color: '#666' }}>
              {progress?.stage || t('初始化')}
              {progress?.message && ` - ${progress.message}`}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

export default NLExtractor;
