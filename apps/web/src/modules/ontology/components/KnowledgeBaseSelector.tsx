/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useCallback } from 'react';
import {
  Card, List, Checkbox, Space, Tag, Spin, Alert, Input, Button, Progress, message, Empty,
} from 'antd';
import {
  DatabaseOutlined, SearchOutlined, FileTextOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { ontologyApi } from '../services/ontologyApi';
import { useExtractionProgress } from '../hooks/useExtractionProgress';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export interface KnowledgeBaseSelectorProps {
  ontologyId: string;
  onExtractionComplete?: (result: any) => void;
}

interface KnowledgeBaseItem {
  kb_id: string;
  name: string;
  description?: string;
  knowledge_count?: number;
  created_at?: string;
}

interface DocumentItem {
  doc_id: string;
  kb_id: string;
  title: string;
  content_type?: string;
  file_type?: string;
  file_size?: number;
  status?: string;
  graph_built?: boolean;
}

export function KnowledgeBaseSelector({ ontologyId, onExtractionComplete }: KnowledgeBaseSelectorProps) {
  const { t } = useI18n('ontology');
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseItem[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<string>('');
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const [searchText, setSearchText] = useState('');
  const [loaded, setLoaded] = useState(false);

  const { progress } = useExtractionProgress(sessionId || null);

  const loadKnowledgeBases = useCallback(async () => {
    setLoading(true);
    try {
      const result = await apiClient.get('/api/knowledge-bases') as any;
      const list = result?.knowledge_bases || result?.data || result || [];
      setKnowledgeBases(Array.isArray(list) ? list : []);
      setLoaded(true);
    } catch {
      setKnowledgeBases([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSelectKb = useCallback(async (kbId: string) => {
    setSelectedKbId(kbId);
    setSelectedDocIds(new Set());
    try {
      const result = await apiClient.get(`/api/knowledge-bases/${kbId}/documents`) as any;
      const docs = result?.documents || result?.data || result || [];
      setDocuments(Array.isArray(docs) ? docs : []);
      setSelectedDocIds(new Set(Array.isArray(docs) ? docs.map((d: DocumentItem) => d.doc_id) : []));
    } catch {
      setDocuments([]);
    }
  }, []);

  const toggleDoc = useCallback((docId: string) => {
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  }, []);

  const handleExtract = useCallback(async () => {
    if (!selectedKbId) {
      message.warning(t('选择知识库'));
      return;
    }
    if (selectedDocIds.size === 0) {
      message.warning(t('请至少选择一篇文档'));
      return;
    }

    setExtracting(true);
    setSessionId('');

    try {
      const result = await ontologyApi.extraction.extractKB({
        ontology_id: ontologyId,
        kb_id: selectedKbId,
        document_ids: Array.from(selectedDocIds),
      });
      setSessionId(result?.session_id || '');
      message.success(t('知识库提取完成'));
      onExtractionComplete?.(result);
    } catch (e) {
      message.error(t('extraction.kbExtractFailed', { msg: (e as Error).message }));
    } finally {
      setExtracting(false);
    }
  }, [selectedKbId, selectedDocIds, ontologyId, onExtractionComplete]);

  const filteredKbs = knowledgeBases.filter((kb) =>
    !searchText || kb.name.toLowerCase().includes(searchText.toLowerCase()),
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Alert
        type="info"
        showIcon
        title={t('从知识库中选择文档进行增量提取')}
        description={t('系统将逐篇解析文档内容，使用增量提取合并知识结构')}
      />

      <Space>
        <Input
          placeholder={t('搜索知识库...')}
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
          style={{ width: 300 }}
        />
        <Button icon={<ReloadOutlined />} onClick={loadKnowledgeBases} loading={loading}>
          {t('刷新')}
        </Button>
      </Space>

      {!loaded ? (
        <Empty description={t('未加载知识库')} image={Empty.PRESENTED_IMAGE_SIMPLE}>
          <Button type="primary" icon={<DatabaseOutlined />} onClick={loadKnowledgeBases} loading={loading}>
            {t('加载知识库列表')}
          </Button>
        </Empty>
      ) : (
        <Spin spinning={loading}>
          <Card title={t('选择知识库')} size="small" style={{ maxHeight: 300, overflow: 'auto' }}>
            {filteredKbs.length === 0 ? (
              <Alert type="warning" title={t('暂无知识库')} description={t('请先在知识库管理中创建知识库并上传文档')} />
            ) : (
              <List
                size="small"
                dataSource={filteredKbs}
                renderItem={(kb) => (
                  <List.Item
                    style={{
                      cursor: 'pointer',
                      background: selectedKbId === kb.kb_id ? '#e6f4ff' : undefined,
                      padding: '8px 12px',
                      borderRadius: 6,
                    }}
                    onClick={() => handleSelectKb(kb.kb_id)}
                  >
                    <List.Item.Meta
                      avatar={<DatabaseOutlined style={{ fontSize: 20, color: '#1677ff' }} />}
                      title={kb.name}
                      description={t('extraction.kbDocCount', { count: kb.knowledge_count || 0 })}
                    />
                    {selectedKbId === kb.kb_id && <Tag color="blue">{t('已选择')}</Tag>}
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Spin>
      )}

      {selectedKbId && documents.length > 0 && (
        <Card
          title={t('extraction.docList', { selected: selectedDocIds.size, total: documents.length })}
          size="small"
          extra={
            <Space>
              <Button size="small" onClick={() => setSelectedDocIds(new Set(documents.map((d) => d.doc_id)))}>
                {t('全选')}
              </Button>
              <Button size="small" onClick={() => setSelectedDocIds(new Set())}>
                {t('取消全选')}
              </Button>
            </Space>
          }
        >
          <List
            size="small"
            dataSource={documents}
            style={{ maxHeight: 250, overflow: 'auto' }}
            renderItem={(doc) => (
              <List.Item style={{ padding: '4px 0' }}>
                <Checkbox
                  checked={selectedDocIds.has(doc.doc_id)}
                  onChange={() => toggleDoc(doc.doc_id)}
                >
                  <FileTextOutlined style={{ marginRight: 8 }} />
                  {doc.title}
                </Checkbox>
              </List.Item>
            )}
          />
        </Card>
      )}

      {extracting && (
        <Card title={t('提取进度')} size="small">
          <Progress
            percent={progress?.progress_percent || 0}
            showInfo={true}
            strokeColor={{
              '0%': '#10B981',
              '100%': '#3B82F6',
            }}
            status="active"
          />
          <div style={{ marginTop: 12, color: '#666' }}>
            {progress?.stage || t('初始化')}
            {progress?.message && ` - ${progress.message}`}
          </div>
        </Card>
      )}

      <div style={{ textAlign: 'right' }}>
        <Button
          type="primary"
          icon={<DatabaseOutlined />}
          onClick={handleExtract}
          loading={extracting}
          disabled={!selectedKbId || selectedDocIds.size === 0}
          size="large"
        >
          {t('开始提取')}
        </Button>
      </div>
    </div>
  );
}

export default KnowledgeBaseSelector;
