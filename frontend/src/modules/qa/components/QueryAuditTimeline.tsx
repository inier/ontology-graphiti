/**
 * 审计时间线 - 展示查询审计记录
 */
import React from 'react';
import { Timeline, Typography, Tag, Space, Empty, Spin, Pagination } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import {
  ClockCircleOutlined,
  SearchOutlined,
  ApiOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import type { AuditRecord } from '../services/nlQueryApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

const PILLAR_ICON: Record<string, React.ReactNode> = {
  bm25: <SearchOutlined />,
  vector: <ApiOutlined />,
  graph: <BranchesOutlined />,
};

interface QueryAuditTimelineProps {
  records: AuditRecord[];
  total: number;
  loading?: boolean;
  onPageChange?: (offset: number) => void;
  pageSize?: number;
}

export function QueryAuditTimeline({
  records,
  total,
  loading,
  onPageChange,
  pageSize = 10,
}: QueryAuditTimelineProps) {
  const { t } = useI18n('qa');

  if (records.length === 0 && !loading) {
    return (
      <Card size="small">
        <Empty description={t('audit.empty')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return ts;
    }
  };

  return (
    <Card size="small" title={t('audit.title')} style={{ marginBottom: 12 }}>
      <Spin spinning={!!loading}>
      <Timeline
        items={records.map((r) => ({
          color: r.total_time_ms < 500 ? 'green' : r.total_time_ms < 2000 ? 'blue' : 'red',
          dot: <ClockCircleOutlined />,
          children: (
            <div style={{ paddingBottom: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text strong style={{ fontSize: 13, maxWidth: '70%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {r.original_query}
                </Text>
                <Space size={4}>
                  {r.selected_pillars.map((p) => (
                    <Tag key={p} icon={PILLAR_ICON[p]} style={{ fontSize: 10, margin: 0 }} color={p === 'bm25' ? 'blue' : p === 'vector' ? 'green' : 'orange'}>
                      {p}
                    </Tag>
                  ))}
                </Space>
              </div>
              <div style={{ marginTop: 4 }}>
                <Space size={8}>
                  <Text type="secondary" style={{ fontSize: 11 }}>{formatTime(r.timestamp)}</Text>
                  <Text style={{ fontSize: 11, color: r.total_time_ms < 500 ? '#52c41a' : r.total_time_ms < 2000 ? '#1890ff' : '#ff4d4f' }}>
                    {r.total_time_ms.toFixed(0)}ms
                  </Text>
                  <Tag icon={<CheckCircleOutlined />} color="success" style={{ fontSize: 10, margin: 0 }}>
                    {t('audit.sourceCount', { count: r.source_count })}
                  </Tag>
                  <Text type="secondary" style={{ fontSize: 11 }}>{r.intent}</Text>
                </Space>
              </div>
              {r.extracted_entities.length > 0 && (
                <div style={{ marginTop: 2 }}>
                  {r.extracted_entities.slice(0, 3).map((e, i) => (
                    <Tag key={i} style={{ fontSize: 10, marginBottom: 0 }} color="processing">{e}</Tag>
                  ))}
                  {r.extracted_entities.length > 3 && (
                    <Text type="secondary" style={{ fontSize: 10 }}>{t('audit.moreEntities', { count: r.extracted_entities.length - 3 })}</Text>
                  )}
                </div>
              )}
            </div>
          ),
        }))}
      />
      {total > pageSize && onPageChange && (
        <Pagination
          size="small"
          total={total}
          pageSize={pageSize}
          onChange={(page) => onPageChange((page - 1) * pageSize)}
          style={{ textAlign: 'center', marginTop: 8 }}
        />
      )}
      </Spin>
    </Card>
  );
}
