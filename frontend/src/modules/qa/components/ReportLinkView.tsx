import React from 'react';
import { Typography, Space } from 'antd';
import { FileTextOutlined, ArrowRightOutlined } from '@ant-design/icons';
import type { ReportLink } from '../hooks/useQAI';

const { Text } = Typography;

export function ReportLinkView({ report }: { report: ReportLink }) {
  return (
    <div
      style={{
        margin: '8px 0',
        padding: '10px 14px',
        borderRadius: 8,
        border: '1px solid #d9d9d9',
        background: '#fff',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        transition: 'border-color 0.2s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = '#1890ff')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = '#d9d9d9')}
      onClick={() => {
        window.open(`/reports/${report.report_id}`, '_blank');
      }}
    >
      <Space>
        <FileTextOutlined style={{ color: '#1890ff', fontSize: 18 }} />
        <div>
          <Text strong style={{ fontSize: 13 }}>{report.title}</Text>
          {report.summary && (
            <div><Text type="secondary" style={{ fontSize: 12 }}>{report.summary}</Text></div>
          )}
          {report.created_at && (
            <div><Text type="secondary" style={{ fontSize: 11 }}>{report.created_at}</Text></div>
          )}
        </div>
      </Space>
      <ArrowRightOutlined style={{ color: '#999' }} />
    </div>
  );
}
