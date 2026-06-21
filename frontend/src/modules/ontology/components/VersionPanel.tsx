import { useState, useEffect } from 'react';
import { Timeline, Tag, Button as AntButton, Space, Input, Modal, Select as AntSelect, Row, Col, Empty, Spin, Popconfirm, message } from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import { ProCard as Card } from '@ant-design/pro-components';
import { RollbackOutlined, SwapOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import adapter from '@/modules/shared/components/adapter';
import { useVersionStore } from '../stores/versionStore';
import type { VersionInfo } from '../stores/versionStore';
import { getCurrentLocale } from '@/modules/shared/stores/i18nStore';

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
  const { t } = useI18n('ontology');
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
      adapter.getMessage().success(t('versionPanel.versionCreated'));
    } catch {
      // validation error
    }
  };

  const handleRollback = async (versionId: string) => {
    await rollbackVersion(documentId, versionId);
    adapter.getMessage().success(t('versionPanel.rollbackSuccess'));
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
        adapter.getMessage().success(t('versionPanel.temporalComplete'));
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
            {t('versionPanel.createVersion')}
          </Button>
          <Button
            type={compareMode ? 'primary' : 'default'}
            onClick={() => {
              setCompareMode(!compareMode);
              setSelectedForCompare([]);
            }}
          >
            <SwapOutlined /> {t('versionPanel.compare')}
          </Button>
        </Space>
      </Space>

      {compareMode && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space>
            <span>{t('versionPanel.selected', { count: selectedForCompare.length })}</span>
            <Button
              onClick={handleCompare}
              disabled={selectedForCompare.length !== 2}
            >
              {t('versionPanel.executeCompare')}
            </Button>
          </Space>
        </Card>
      )}

      {comparisonResult && (
        <Card size="small" title={t('versionPanel.compareResult')} style={{ marginBottom: 16 }}>
          <Row gutter={[8, 8]}>
            <Col span={8}>
              <Card size="small" title={t('versionPanel.addedTypes')}>
                {comparisonResult.added_types.length === 0 ? (
                  <span style={{ color: '#999' }}>{t('versionPanel.none')}</span>
                ) : (
                  comparisonResult.added_types.map((tp) => (
                    <Tag key={tp} color="green">{tp}</Tag>
                  ))
                )}
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" title={t('versionPanel.deletedTypes')}>
                {comparisonResult.removed_types.length === 0 ? (
                  <span style={{ color: '#999' }}>{t('versionPanel.none')}</span>
                ) : (
                  comparisonResult.removed_types.map((tp) => (
                    <Tag key={tp} color="red">{tp}</Tag>
                  ))
                )}
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" title={t('versionPanel.modifiedTypes')}>
                {comparisonResult.modified_types.length === 0 ? (
                  <span style={{ color: '#999' }}>{t('versionPanel.none')}</span>
                ) : (
                  comparisonResult.modified_types.map((tp) => (
                    <Tag key={tp.type_name} color="orange">{tp.type_name}</Tag>
                  ))
                )}
              </Card>
            </Col>
          </Row>
        </Card>
      )}

      <Card size="small" title={t('versionPanel.temporalQuery')} style={{ marginBottom: 16 }}>
        <Space>
          <Input
            placeholder={t('versionPanel.temporalPlaceholder')}
            value={temporalInput}
            onChange={(e) => setTemporalInput(e.target.value)}
            style={{ width: 240 }}
          />
          <Button onClick={handleTemporalQuery}>
            <ClockCircleOutlined /> {t('versionPanel.query')}
          </Button>
        </Space>
      </Card>

      <Spin spinning={loading}>
        {versions.length === 0 ? (
          <Empty description={t('versionPanel.noVersion')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
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
                        {new Date(v.created_at).toLocaleString(getCurrentLocale())} · {v.entity_count} {t('versionPanel.entity')} · {v.relation_count} {t('versionPanel.relation')}
                      </div>
                    </div>
                    <Popconfirm
                      title={t('versionPanel.rollbackConfirm')}
                      onConfirm={() => handleRollback(v.version_id)}
                    >
                      <AntButton
                        type="text"
                        size="small"
                        icon={<RollbackOutlined />}
                        disabled={v.status === 'archived'}
                      >
                        {t('versionPanel.rollback')}
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
        title={t('versionPanel.createVersion')}
        open={createModalVisible}
        onOk={handleCreate}
        onCancel={() => {
          setCreateModalVisible(false);
          createForm.resetFields();
        }}
        okText={t('versionPanel.create')}
        cancelText={t('versionPanel.cancel')}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="changelog"
            label={t('versionPanel.changelog')}
            rules={[{ required: true, message: t('versionPanel.changelogRequired') }]}
          >
            <Input.TextArea rows={3} placeholder={t('versionPanel.changelogPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
