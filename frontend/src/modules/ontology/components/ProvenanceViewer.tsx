/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useCallback } from 'react';
import {
  Drawer, Descriptions, Tag, Button, Space, Empty, Spin, message,
} from 'antd';
import {
  LinkOutlined, FileSearchOutlined, ClockCircleOutlined,
  ExperimentOutlined, TagOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';

export interface ProvenanceViewerProps {
  entityId: string;
  entityType?: string;
  visible: boolean;
  onClose: () => void;
}

interface ProvenanceRecord {
  entity_id: string;
  source_doc_id: string;
  source_doc_name?: string;
  vector_chunk_id?: string;
  doc_fragment_id?: string;
  timestamp: string;
  extraction_method?: string;
  he_template_version?: string;
  confidence?: number;
}

export function ProvenanceViewer({
  entityId, entityType, visible, onClose,
}: ProvenanceViewerProps) {
  const [provenance, setProvenance] = useState<ProvenanceRecord | null>(null);
  const [loading, setLoading] = useState(false);

  const loadProvenance = useCallback(async () => {
    if (!entityId) return;
    setLoading(true);
    try {
      const result = await apiClient.get(`/api/extraction/provenance/${entityId}`) as any;
      setProvenance(result?.provenance || result || null);
    } catch {
      setProvenance(null);
    } finally {
      setLoading(false);
    }
  }, [entityId]);

  const handleOpen = useCallback(() => {
    if (visible) loadProvenance();
  }, [visible, loadProvenance]);

  useState(() => { if (visible) handleOpen(); });

  const handleViewSource = useCallback(() => {
    if (provenance?.source_doc_id) {
      message.info('跳转到知识库文档详情（待实现）');
    }
  }, [provenance]);

  return (
    <Drawer
      title={
        <Space>
          <FileSearchOutlined />
          溯源信息
        </Space>
      }
      open={visible}
      onClose={onClose}
      width={480}
      afterOpenChange={(open) => { if (open) loadProvenance(); }}
    >
      <Spin spinning={loading}>
        {provenance ? (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="实体 ID">
              <Tag>{provenance.entity_id}</Tag>
            </Descriptions.Item>
            {entityType && (
              <Descriptions.Item label="实体类型">
                <Tag color="blue">{entityType}</Tag>
              </Descriptions.Item>
            )}
            <Descriptions.Item label={
              <Space><FileSearchOutlined /> 来源文档</Space>
            }>
              {provenance.source_doc_name || provenance.source_doc_id}
              <Button
                type="link"
                size="small"
                icon={<LinkOutlined />}
                onClick={handleViewSource}
              >
                查看原文
              </Button>
            </Descriptions.Item>
            {provenance.vector_chunk_id && (
              <Descriptions.Item label="向量切片 ID">
                <Tag color="geekblue">{provenance.vector_chunk_id}</Tag>
              </Descriptions.Item>
            )}
            {provenance.doc_fragment_id && (
              <Descriptions.Item label="文档碎片 ID">
                <Tag color="purple">{provenance.doc_fragment_id}</Tag>
              </Descriptions.Item>
            )}
            <Descriptions.Item label={
              <Space><ClockCircleOutlined /> 提取时间</Space>
            }>
              {provenance.timestamp}
            </Descriptions.Item>
            {provenance.extraction_method && (
              <Descriptions.Item label={
                <Space><ExperimentOutlined /> 提取方法</Space>
              }>
                <Tag color="green">{provenance.extraction_method}</Tag>
              </Descriptions.Item>
            )}
            {provenance.he_template_version && (
              <Descriptions.Item label={
                <Space><TagOutlined /> HE 模板版本</Space>
              }>
                {provenance.he_template_version}
              </Descriptions.Item>
            )}
            {provenance.confidence !== undefined && (
              <Descriptions.Item label="置信度">
                <Tag color={provenance.confidence >= 0.8 ? 'green' : provenance.confidence >= 0.5 ? 'orange' : 'red'}>
                  {(provenance.confidence * 100).toFixed(1)}%
                </Tag>
              </Descriptions.Item>
            )}
          </Descriptions>
        ) : (
          <Empty description="暂无溯源信息" />
        )}
      </Spin>
    </Drawer>
  );
}

export default ProvenanceViewer;
