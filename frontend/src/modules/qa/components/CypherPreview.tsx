/**
 * Cypher 预览 - 展示生成的 Cypher 查询
 */
import React from 'react';
import { Card, Typography, Tag, Space, Tooltip } from 'antd';
import { CodeOutlined, SafetyCertificateOutlined, CopyOutlined } from '@ant-design/icons';

const { Paragraph } = Typography;

interface CypherPreviewProps {
  cypher?: string | null;
  validated?: boolean;
  source?: string;
}

export function CypherPreview({ cypher, validated, source }: CypherPreviewProps) {
  if (!cypher) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(cypher);
  };

  return (
    <Card
      size="small"
      title={
        <Space>
          <CodeOutlined />
          <span>生成的 Cypher 查询</span>
          {validated !== undefined && (
            <Tag
              icon={<SafetyCertificateOutlined />}
              color={validated ? 'success' : 'error'}
              style={{ fontSize: 11 }}
            >
              {validated ? '已校验' : '校验失败'}
            </Tag>
          )}
          {source && <Tag style={{ fontSize: 11 }}>{source}</Tag>}
        </Space>
      }
      extra={
        <Tooltip title="复制">
          <CopyOutlined style={{ cursor: 'pointer', color: '#999' }} onClick={handleCopy} />
        </Tooltip>
      }
      style={{ marginBottom: 8 }}
      styles={{ body: { padding: '8px 12px' } }}
    >
      <Paragraph
        style={{
          margin: 0,
          fontFamily: 'Consolas, Monaco, "Courier New", monospace',
          fontSize: 12,
          lineHeight: 1.6,
          background: '#f5f5f5',
          padding: '8px 10px',
          borderRadius: 4,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}
      >
        {cypher}
      </Paragraph>
    </Card>
  );
}
