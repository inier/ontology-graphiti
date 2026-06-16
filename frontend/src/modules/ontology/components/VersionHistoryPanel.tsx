import { useState, useEffect, useCallback } from 'react';
import { Timeline, Tag, Button, Popconfirm, Empty, Spin, Space, message } from 'antd';
import { RollbackOutlined, SwapOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useOntologyStore } from '../stores/ontologyStore';
import type { SchemaVersion } from '../stores/ontologyStore';
import { ontologyApi } from '../services/ontologyApi';

export interface VersionHistoryPanelProps {
  ontologyId: string;
  onRollback?: (versionId: string) => void;
  onDiff?: (versionIdA: string, versionIdB: string) => void;
}

export function VersionHistoryPanel({ ontologyId, onRollback, onDiff }: VersionHistoryPanelProps) {
  const { schemaVersions, loadSchemaVersions, loading } = useOntologyStore();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [compareMode, setCompareMode] = useState(false);

  useEffect(() => {
    if (ontologyId) {
      loadSchemaVersions();
    }
  }, [ontologyId, loadSchemaVersions]);

  const handleSelect = useCallback((versionId: string) => {
    if (!compareMode) return;
    setSelectedIds((prev) => {
      if (prev.includes(versionId)) {
        return prev.filter((id) => id !== versionId);
      }
      if (prev.length >= 2) {
        return [prev[1], versionId];
      }
      return [...prev, versionId];
    });
  }, [compareMode]);

  const handleCompare = useCallback(() => {
    if (selectedIds.length === 2 && onDiff) {
      onDiff(selectedIds[0], selectedIds[1]);
    }
  }, [selectedIds, onDiff]);

  const handleRollback = useCallback(async (versionId: string) => {
    try {
      await ontologyApi.schemaVersions.rollback(ontologyId, versionId);
      message.success('回滚成功');
      await loadSchemaVersions();
      onRollback?.(versionId);
    } catch (e) {
      message.error(`回滚失败: ${(e as Error).message}`);
    }
  }, [ontologyId, loadSchemaVersions, onRollback]);

  const toggleCompareMode = useCallback(() => {
    setCompareMode((prev) => !prev);
    setSelectedIds([]);
  }, []);

  const isStable = (version: SchemaVersion) =>
    version.status === 'published' || version.status === 'ACTIVE' || version.status === 'stable';

  const statusColor = (status: string): string => {
    switch (status) {
      case 'published':
      case 'ACTIVE':
      case 'stable':
        return 'green';
      case 'draft':
      case 'DRAFT':
        return 'blue';
      case 'archived':
      case 'ARCHIVED':
        return 'orange';
      default:
        return 'default';
    }
  };

  const statusLabel = (status: string): string => {
    switch (status) {
      case 'published':
      case 'ACTIVE':
      case 'stable':
        return 'stable';
      case 'draft':
      case 'DRAFT':
        return 'draft';
      case 'archived':
      case 'ARCHIVED':
        return 'archived';
      default:
        return status;
    }
  };

  if (loading) {
    return <Spin spinning style={{ display: 'block', width: '100%', minHeight: 80 }} />;
  }

  return (
    <div>
      <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }}>
        <span style={{ fontWeight: 500 }}>版本历史</span>
        <Space>
          <Button
            size="small"
            type={compareMode ? 'primary' : 'default'}
            icon={<SwapOutlined />}
            onClick={toggleCompareMode}
          >
            {compareMode ? '取消对比' : '版本对比'}
          </Button>
          {compareMode && selectedIds.length === 2 && (
            <Button size="small" type="primary" icon={<CheckCircleOutlined />} onClick={handleCompare}>
              查看差异
            </Button>
          )}
        </Space>
      </Space>

      {compareMode && (
        <div style={{
          marginBottom: 12,
          padding: '8px 12px',
          background: '#f6f8fa',
          borderRadius: 6,
          fontSize: 13,
          color: '#666',
        }}>
          点击选择两个版本进行对比（已选 {selectedIds.length}/2）
          {selectedIds.length > 0 && (
            <div style={{ marginTop: 4 }}>
              {selectedIds.map((id, idx) => {
                const v = schemaVersions.find((sv) => sv.id === id);
                return v ? (
                  <Tag key={id} color="blue" style={{ marginRight: 4 }}>
                    {idx === 0 ? 'A' : 'B'}: v{v.version_number}
                  </Tag>
                ) : null;
              })}
            </div>
          )}
        </div>
      )}

      {schemaVersions.length === 0 ? (
        <Empty description="暂无版本记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <Timeline
          items={schemaVersions.map((version: SchemaVersion) => ({
            color: isStable(version) ? 'green' : 'blue',
            children: (
              <div
                onClick={() => handleSelect(version.id)}
                style={{
                  padding: '8px 12px',
                  borderRadius: 6,
                  border: compareMode && selectedIds.includes(version.id)
                    ? '2px solid #1890ff'
                    : '1px solid #f0f0f0',
                  cursor: compareMode ? 'pointer' : 'default',
                  background: compareMode && selectedIds.includes(version.id)
                    ? '#e6f7ff'
                    : '#fff',
                  transition: 'all 0.2s',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ flex: 1 }}>
                    <Space>
                      <strong>v{version.version_number}</strong>
                      {isStable(version) && <Tag color="green">stable</Tag>}
                      <Tag color={statusColor(version.status)}>{statusLabel(version.status)}</Tag>
                    </Space>
                    <div style={{ color: '#666', fontSize: 13, marginTop: 4 }}>
                      {version.changelog || '无变更说明'}
                    </div>
                    <div style={{ color: '#999', fontSize: 12, marginTop: 2 }}>
                      {new Date(version.created_at).toLocaleString('zh-CN')}
                      {version.created_by && ` · ${version.created_by}`}
                    </div>
                  </div>
                  <Popconfirm
                    title="确认回滚到此版本？"
                    description="仅回滚类型定义，不影响实例数据"
                    onConfirm={() => handleRollback(version.id)}
                    okText="确认回滚"
                    cancelText="取消"
                  >
                    <Button
                      type="text"
                      size="small"
                      icon={<RollbackOutlined />}
                      danger
                    >
                      回滚到此版本
                    </Button>
                  </Popconfirm>
                </div>
              </div>
            ),
          }))}
        />
      )}
    </div>
  );
}
