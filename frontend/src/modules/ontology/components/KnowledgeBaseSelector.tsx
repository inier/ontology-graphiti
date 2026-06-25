/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useCallback } from 'react';
import {
  Card, List, Checkbox, Space, Tag, Spin, Alert, Input, Button, Progress, message,
} from 'antd';
import {
  DatabaseOutlined, SearchOutlined, FileTextOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { ontologyApi } from '../services/ontologyApi';

export interface KnowledgeBaseSelectorProps {
  ontologyId: string;
  onExtractionComplete?: (result: any) => void;
}

interface KnowledgeBaseItem {
  id: string;
  name: string;
  description?: string;
  document_count?: number;
  created_at?: string;
}

interface DocumentItem {
  id: string;
  name: string;
  status?: string;
  size?: number;
}

export function KnowledgeBaseSelector({ ontologyId, onExtractionComplete }: KnowledgeBaseSelectorProps) {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseItem[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<string>('');
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [searchText, setSearchText] = useState('');
  const [loaded, setLoaded] = useState(false);

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
      const docs = result?.documents || result?.data || [];
      setDocuments(Array.isArray(docs) ? docs : []);
      setSelectedDocIds(new Set(Array.isArray(docs) ? docs.map((d: DocumentItem) => d.id) : []));
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
      message.warning('请先选择知识库');
      return;
    }
    if (selectedDocIds.size === 0) {
      message.warning('请至少选择一篇文档');
      return;
    }

    setExtracting(true);
    setProgress({ current: 0, total: selectedDocIds.size });

    try {
      const result = await ontologyApi.extraction.extractKB({
        ontology_id: ontologyId,
        kb_id: selectedKbId,
        document_ids: Array.from(selectedDocIds),
      });
      setProgress({ current: selectedDocIds.size, total: selectedDocIds.size });
      message.success('知识库提取完成');
      onExtractionComplete?.(result);
    } catch (e) {
      message.error(`知识库提取失败: ${(e as Error).message}`);
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
        message="从知识库中选择文档进行增量提取"
        description="系统将逐篇解析文档内容，使用增量提取合并知识结构"
      />

      <Space>
        <Input
          placeholder="搜索知识库..."
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
          style={{ width: 300 }}
        />
        <Button icon={<ReloadOutlined />} onClick={loadKnowledgeBases} loading={loading}>
          刷新
        </Button>
      </Space>

      {!loaded ? (
        <Card size="small">
          <div style={{ textAlign: 'center', padding: 20 }}>
            <Button type="primary" icon={<DatabaseOutlined />} onClick={loadKnowledgeBases} loading={loading}>
              加载知识库列表
            </Button>
          </div>
        </Card>
      ) : (
        <Spin spinning={loading}>
          <Card title="选择知识库" size="small" style={{ maxHeight: 300, overflow: 'auto' }}>
            {filteredKbs.length === 0 ? (
              <Alert type="warning" message="暂无知识库" description="请先在知识库管理中创建知识库并上传文档" />
            ) : (
              <List
                size="small"
                dataSource={filteredKbs}
                renderItem={(kb) => (
                  <List.Item
                    style={{
                      cursor: 'pointer',
                      background: selectedKbId === kb.id ? '#e6f4ff' : undefined,
                      padding: '8px 12px',
                      borderRadius: 6,
                    }}
                    onClick={() => handleSelectKb(kb.id)}
                  >
                    <List.Item.Meta
                      avatar={<DatabaseOutlined style={{ fontSize: 20, color: '#1677ff' }} />}
                      title={kb.name}
                      description={`${kb.document_count || 0} 篇文档`}
                    />
                    {selectedKbId === kb.id && <Tag color="blue">已选择</Tag>}
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Spin>
      )}

      {selectedKbId && documents.length > 0 && (
        <Card
          title={`文档列表 (${selectedDocIds.size}/${documents.length})`}
          size="small"
          extra={
            <Space>
              <Button size="small" onClick={() => setSelectedDocIds(new Set(documents.map((d) => d.id)))}>
                全选
              </Button>
              <Button size="small" onClick={() => setSelectedDocIds(new Set())}>
                取消全选
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
                  checked={selectedDocIds.has(doc.id)}
                  onChange={() => toggleDoc(doc.id)}
                >
                  <FileTextOutlined style={{ marginRight: 8 }} />
                  {doc.name}
                </Checkbox>
              </List.Item>
            )}
          />
        </Card>
      )}

      {extracting && progress.total > 0 && (
        <Progress
          percent={Math.round((progress.current / progress.total) * 100)}
          status="active"
          format={() => `已处理 ${progress.current}/${progress.total} 篇文档`}
        />
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
          开始提取
        </Button>
      </div>
    </div>
  );
}

export default KnowledgeBaseSelector;
