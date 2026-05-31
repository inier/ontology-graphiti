import { useState, useEffect } from 'react';
import { Card, Timeline, Tag, Button as AntButton, Space, Input, Modal, Form, Select as AntSelect, Row, Col, Empty, Spin, Popconfirm, message } from 'antd';
import { RollbackOutlined, SwapOutlined, ClockCircleOutlined } from '@ant-design/icons';
import adapter from '../../shared/components/adapter';
import { useVersionStore } from '../stores/versionStore';
import type { VersionInfo } from '../stores/versionStore';

interface VersionPanelProps {
  documentId: string;
}

const Button = adapter.getButton();

const STATUS_COLORS: Record<string, string> = {
  draft: 'default',
  published: 'green',
  archived: 'orange',
};

export function VersionPanel({ documentId }: VersionPanelProps) {
  const {
    versions,
    comparisonResult,
    loading,
    loadVersions,
    createVersion,
    rollbackVersion,
    compareVersions,
    temporalQuery,
  } = useVersionStore();

  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [compareMode, setCompareMode] = useState(false);
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([]);
  const [temporalInput, setTemporalInput] = useState('');
  const [createForm] = Form.useForm();

  useEffect(() => {
    loadVersions(documentId);
  }, [documentId]);

  const handleCreate = async () => {
    try {
      const values = await createForm.validateFields();
      await createVersion(documentId, values.changelog);
      setCreateModalVisible(false);
      createForm.resetFields();
      adapter.getMessage().success('版本创建成功');
    } catch {
      // validation error
    }
  };

  const handleRollback = async (versionId: string) => {
    await rollbackVersion(documentId, versionId);
    adapter.getMessage().success('回滚成功');
    loadVersions(documentId);
  };

  const handleCompare = async () => {
    if (selectedForCompare.length === 2) {
      await compareVersions(documentId, selectedForCompare[0], selectedForCompare[1]);
    }
  };

  const handleTemporalQuery = async () => {
    if (temporalInput) {
      const result = await temporalQuery(documentId, temporalInput);
      if (result) {
        adapter.getMessage().success('时序查询完成');
      }
    }
  };

  const toggleCompareSelection = (versionId: string) => {
    setSelectedForCompare((prev) => {
      if (prev.includes(versionId)) {
        return prev.filter((id) => id !== versionId);
      }
      if (prev.length >= 2) {
        return [prev[1], versionId];
      }
      return [...prev, versionId];
    });
  };

  return (
    <div>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Space>
          <Button type="primary" onClick={() => setCreateModalVisible(true)}>
            创建版本
          </Button>
          <Button
            type={compareMode ? 'primary' : 'default'}
            onClick={() => {
              setCompareMode(!compareMode);
              setSelectedForCompare([]);
            }}
          >
            <SwapOutlined /> 对比
          </Button>
        </Space>
      </Space>

      {compareMode && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space>
            <span>已选择 {selectedForCompare.length}/2 个版本</span>
            <Button
              onClick={handleCompare}
              disabled={selectedForCompare.length !== 2}
            >
              执行对比
            </Button>
          </Space>
        </Card>
      )}

      {comparisonResult && (
        <Card size="small" title="对比结果" style={{ marginBottom: 16 }}>
          <Row gutter={[8, 8]}>
            <Col span={8}>
              <Card size="small" title="新增类型">
                {comparisonResult.added_types.length === 0 ? (
                  <span style={{ color: '#999' }}>无</span>
                ) : (
                  comparisonResult.added_types.map((t) => (
                    <Tag key={t} color="green">{t}</Tag>
                  ))
                )}
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" title="删除类型">
                {comparisonResult.removed_types.length === 0 ? (
                  <span style={{ color: '#999' }}>无</span>
                ) : (
                  comparisonResult.removed_types.map((t) => (
                    <Tag key={t} color="red">{t}</Tag>
                  ))
                )}
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" title="修改类型">
                {comparisonResult.modified_types.length === 0 ? (
                  <span style={{ color: '#999' }}>无</span>
                ) : (
                  comparisonResult.modified_types.map((t) => (
                    <Tag key={t.type_name} color="orange">{t.type_name}</Tag>
                  ))
                )}
              </Card>
            </Col>
          </Row>
        </Card>
      )}

      <Card size="small" title="时序查询" style={{ marginBottom: 16 }}>
        <Space>
          <Input
            placeholder="输入时间点 (ISO格式)"
            value={temporalInput}
            onChange={(e) => setTemporalInput(e.target.value)}
            style={{ width: 240 }}
          />
          <Button onClick={handleTemporalQuery}>
            <ClockCircleOutlined /> 查询
          </Button>
        </Space>
      </Card>

      <Spin spinning={loading}>
        {versions.length === 0 ? (
          <Empty description="暂无版本" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <Timeline
            items={versions.map((v: VersionInfo) => ({
              color: v.status === 'published' ? 'green' : 'blue',
              children: (
                <Card
                  size="small"
                  style={{
                    marginBottom: 4,
                    border: compareMode && selectedForCompare.includes(v.version_id)
                      ? '2px solid #1890ff'
                      : undefined,
                    cursor: compareMode ? 'pointer' : 'default',
                  }}
                  onClick={compareMode ? () => toggleCompareSelection(v.version_id) : undefined}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <Space>
                        <strong>v{v.version_number}</strong>
                        <Tag color={STATUS_COLORS[v.status] || 'default'}>{v.status}</Tag>
                      </Space>
                      <div style={{ color: '#666', fontSize: 12, marginTop: 4 }}>
                        {v.changelog}
                      </div>
                      <div style={{ color: '#999', fontSize: 11, marginTop: 2 }}>
                        {new Date(v.created_at).toLocaleString('zh-CN')} · {v.entity_count} 实体 · {v.relation_count} 关系
                      </div>
                    </div>
                    <Popconfirm
                      title="确认回滚到此版本？"
                      onConfirm={() => handleRollback(v.version_id)}
                    >
                      <AntButton
                        type="text"
                        size="small"
                        icon={<RollbackOutlined />}
                        disabled={v.status === 'archived'}
                      >
                        回滚
                      </AntButton>
                    </Popconfirm>
                  </div>
                </Card>
              ),
            }))}
          />
        )}
      </Spin>

      <Modal
        title="创建版本"
        open={createModalVisible}
        onOk={handleCreate}
        onCancel={() => {
          setCreateModalVisible(false);
          createForm.resetFields();
        }}
        okText="创建"
        cancelText="取消"
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="changelog"
            label="变更说明"
            rules={[{ required: true, message: '请输入变更说明' }]}
          >
            <Input.TextArea rows={3} placeholder="描述本次变更内容" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
