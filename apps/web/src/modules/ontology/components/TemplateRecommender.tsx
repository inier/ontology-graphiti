/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useCallback } from 'react';
import {
  List, Tag, Button, Space, Spin, Alert, Rate, Empty, message,
} from 'antd';
import {
  ThunderboltOutlined, GlobalOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { ontologyApi } from '../services/ontologyApi';

export interface TemplateRecommenderProps {
  ontologyId: string;
  text?: string;
  onSelect?: (template: HETemplate) => void;
}

export interface HETemplate {
  id: string;
  name: string;
  description?: string;
  domain?: string;
  applicable_scenarios?: string[];
  match_score?: number;
  source: 'ontology' | 'preset' | 'web_search';
  version?: string;
}

export function TemplateRecommender({
  text, onSelect,
}: TemplateRecommenderProps) {
  const [templates, setTemplates] = useState<HETemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [selectedId, setSelectedId] = useState<string>('');

  const recommendTemplates = useCallback(async () => {
    if (!text?.trim()) {
      message.warning('请先输入描述文本');
      return;
    }
    setLoading(true);
    try {
      const result = await ontologyApi.extraction.recommendTemplates({
        text: text.trim(),
        top_k: 3,
      }) as any;
      const list = result?.templates || result?.data || [];
      setTemplates(Array.isArray(list) ? list : []);
    } catch {
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  }, [text]);

  const handleWebSearch = useCallback(async () => {
    if (!text?.trim()) {
      message.warning('请先输入描述文本');
      return;
    }
    setSearching(true);
    try {
      const result = await ontologyApi.extraction.generateTemplateWebSearch({
        text: text.trim(),
      }) as any;
      const newTemplate = result?.template || result?.data;
      if (newTemplate) {
        setTemplates((prev) => [
          ...prev,
          { ...newTemplate, source: 'web_search' as const },
        ]);
        message.success('联网搜索生成模板成功');
      }
    } catch (e) {
      message.error(`联网搜索生成失败: ${(e as Error).message}`);
    } finally {
      setSearching(false);
    }
  }, [text]);

  const handleSelect = useCallback((template: HETemplate) => {
    setSelectedId(template.id);
    onSelect?.(template);
  }, [onSelect]);

  const sourceTagColor = (source: HETemplate['source']) => {
    switch (source) {
      case 'ontology': return 'blue';
      case 'preset': return 'green';
      case 'web_search': return 'orange';
      default: return 'default';
    }
  };

  const sourceLabel = (source: HETemplate['source']) => {
    switch (source) {
      case 'ontology': return '本体生成';
      case 'preset': return '预设模板';
      case 'web_search': return '联网搜索';
      default: return source;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Alert
        type="info"
        showIcon
        title="模板推荐"
        description="系统根据您的描述推荐最匹配的提取模板。三级回退：本体定义自动生成 → 预设模板 → 联网搜索动态生成"
      />

      <Spin spinning={loading}>
        {templates.length === 0 && !loading ? (
          <Empty description="暂无推荐模板，请输入描述文本后点击推荐" />
        ) : (
          <List
            size="small"
            dataSource={templates}
            renderItem={(template) => (
              <List.Item
                style={{
                  cursor: 'pointer',
                  background: selectedId === template.id ? '#e6f4ff' : undefined,
                  padding: '8px 12px',
                  borderRadius: 6,
                  border: selectedId === template.id ? '1px solid #1677ff' : '1px solid transparent',
                }}
                onClick={() => handleSelect(template)}
              >
                <List.Item.Meta
                  avatar={
                    template.match_score !== undefined ? (
                      <Rate disabled value={Math.round(template.match_score)} count={3} />
                    ) : null
                  }
                  title={
                    <Space>
                      {template.name}
                      <Tag color={sourceTagColor(template.source)}>
                        {sourceLabel(template.source)}
                      </Tag>
                      {selectedId === template.id && (
                        <CheckCircleOutlined style={{ color: '#1677ff' }} />
                      )}
                    </Space>
                  }
                  description={
                    <div>
                      <div>{template.description || '无描述'}</div>
                      {template.applicable_scenarios && template.applicable_scenarios.length > 0 && (
                        <div style={{ marginTop: 4 }}>
                          {template.applicable_scenarios.map((s, i) => (
                            <Tag key={i}>{s}</Tag>
                          ))}
                        </div>
                      )}
                      {template.domain && (
                        <div style={{ marginTop: 4, color: '#999' }}>
                          领域: {template.domain}
                        </div>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Spin>

      <div style={{ textAlign: 'right' }}>
        <Space>
          <Button
            icon={<ThunderboltOutlined />}
            onClick={recommendTemplates}
            loading={loading}
            disabled={!text?.trim()}
          >
            推荐模板
          </Button>
          <Button
            icon={<GlobalOutlined />}
            onClick={handleWebSearch}
            loading={searching}
            disabled={!text?.trim()}
          >
            联网搜索生成
          </Button>
        </Space>
      </div>
    </div>
  );
}

export default TemplateRecommender;
