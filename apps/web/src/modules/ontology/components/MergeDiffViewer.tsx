/**
 * MergeDiffViewer 组件 —— 3-way merge 可视化对比（FR-032 / T347）
 *
 * 顶部：3 个分支选择器（Base / Ours / Theirs）
 * 主区域：左中右三栏并排对比
 *   - ObjectType 卡片可折叠
 *   - 修改的 property 字段以黄色高亮
 *   - 冲突字段以红色高亮 + 显示 ours vs theirs
 * 底部：冲突解决操作栏
 *   - "Use Ours" / "Use Theirs" / "Manual Edit" 按钮
 * 顶部 "Confirm Merge" 按钮（合并后调用 API）
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, Select, Button, Space, Typography, Tag, Empty, Spin, Alert, Collapse, Input, message, Modal,
} from 'antd';
import {
  BranchesOutlined, CheckOutlined, EditOutlined, SwapOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Title } = Typography;
const { TextArea } = Input;

export interface MergeDiffViewerProps {
  branchId: string;
  baseVersionId?: string;
  onMerged?: (result: unknown) => void;
}

interface PropertyDiff {
  name: string;
  base_value: unknown;
  ours_value: unknown;
  theirs_value: unknown;
  has_conflict: boolean;
  changed_in_ours: boolean;
  changed_in_theirs: boolean;
}

interface ObjectTypeDiff {
  object_type: string;
  removed: boolean;
  added: boolean;
  properties: PropertyDiff[];
}

interface MergeDiffResponse {
  base_version_id?: string;
  ours_version_id?: string;
  theirs_version_id?: string;
  object_types: ObjectTypeDiff[];
  conflict_count: number;
}

interface Resolution {
  object_type: string;
  property_name: string;
  resolution: 'ours' | 'theirs' | 'manual';
  manual_value?: unknown;
}

interface ManualEditState {
  objectType: string;
  property: PropertyDiff;
  value: string;
}

const PROPERTY_HIGHLIGHT = {
  MODIFIED: '#fffbe6',
  CONFLICT: '#fff1f0',
  RESOLVED: '#f6ffed',
};

export function MergeDiffViewer({ branchId, baseVersionId, onMerged }: MergeDiffViewerProps) {
  const { t } = useI18n('ontology');
  void t;
  const [baseVersion, setBaseVersion] = useState<string | undefined>(baseVersionId);
  const [oursVersion, setOursVersion] = useState<string | undefined>(baseVersionId);
  const [theirsVersion, setTheirsVersion] = useState<string | undefined>();
  const [versionOptions, setVersionOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [diff, setDiff] = useState<MergeDiffResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [merging, setMerging] = useState(false);
  const [resolutions, setResolutions] = useState<Record<string, Resolution>>({});
  const [manualEdit, setManualEdit] = useState<ManualEditState | null>(null);

  const fetchVersions = useCallback(async () => {
    try {
      const data = await apiClient.get<{ versions: Array<{ version_id: string; version_number: number }> }>(
        '/api/ontology/versions',
      );
      setVersionOptions(
        (data.versions || []).map((v) => ({ value: v.version_id, label: `v${v.version_number}` })),
      );
    } catch {
      setVersionOptions([]);
    }
  }, []);

  useEffect(() => { void fetchVersions(); }, [fetchVersions]);

  const fetchDiff = useCallback(async () => {
    if (!baseVersion || !oursVersion || !theirsVersion) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({
        base: baseVersion,
        ours: oursVersion,
        theirs: theirsVersion,
      });
      const data = await apiClient.get<MergeDiffResponse>(
        `/api/ontology/branches/${branchId}/diff?${params.toString()}`,
      );
      setDiff(data);
      setResolutions({});
    } catch (e) {
      message.error(`加载 diff 失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [baseVersion, oursVersion, theirsVersion, branchId]);

  useEffect(() => { void fetchDiff(); }, [fetchDiff]);

  const resolutionKey = useCallback(
    (objectType: string, propName: string) => `${objectType}::${propName}`,
    [],
  );

  const setResolution = useCallback(
    (objectType: string, prop: PropertyDiff, resolution: 'ours' | 'theirs' | 'manual', manualValue?: unknown) => {
      const key = resolutionKey(objectType, prop.name);
      setResolutions((prev) => ({
        ...prev,
        [key]: {
          object_type: objectType,
          property_name: prop.name,
          resolution,
          manual_value: manualValue,
        },
      }));
    },
    [resolutionKey],
  );

  const openManualEdit = useCallback((objectType: string, prop: PropertyDiff) => {
    setManualEdit({
      objectType,
      property: prop,
      value: String(prop.ours_value ?? ''),
    });
  }, []);

  const handleConfirmManual = useCallback(() => {
    if (!manualEdit) return;
    setResolution(
      manualEdit.objectType,
      manualEdit.property,
      'manual',
      manualEdit.value,
    );
    setManualEdit(null);
  }, [manualEdit, setResolution]);

  const handleConfirmMerge = useCallback(async () => {
    const conflictItems: Resolution[] = Object.values(resolutions);
    if (diff && diff.conflict_count > 0 && conflictItems.length === 0) {
      message.warning('存在冲突但未指定任何解决方案');
      return;
    }
    setMerging(true);
    try {
      const result = await apiClient.post('/api/ontology/branches/merge', {
        branch_id: branchId,
        base_version_id: baseVersion,
        ours_version_id: oursVersion,
        theirs_version_id: theirsVersion,
        conflicts_resolved: conflictItems,
      });
      message.success('合并已提交');
      onMerged?.(result);
      void fetchDiff();
    } catch (e) {
      message.error(`合并失败: ${(e as Error).message}`);
    } finally {
      setMerging(false);
    }
  }, [resolutions, diff, branchId, baseVersion, oursVersion, theirsVersion, onMerged, fetchDiff]);

  const conflictCount = diff?.conflict_count ?? 0;
  const resolvedCount = useMemo(
    () => Object.keys(resolutions).length,
    [resolutions],
  );
  const remainingConflicts = Math.max(0, conflictCount - resolvedCount);

  const renderValue = (v: unknown) => {
    if (v === null || v === undefined) return <Text type="secondary">(空)</Text>;
    if (typeof v === 'object') return <Text code style={{ fontSize: 12 }}>{JSON.stringify(v)}</Text>;
    return <Text code style={{ fontSize: 12 }}>{String(v)}</Text>;
  };

  const renderPropertyRow = (ot: string, prop: PropertyDiff) => {
    const isConflict = prop.has_conflict;
    const isModified = prop.changed_in_ours || prop.changed_in_theirs;
    const key = resolutionKey(ot, prop.name);
    const resolved = resolutions[key];
    const bg = resolved
      ? PROPERTY_HIGHLIGHT.RESOLVED
      : isConflict
        ? PROPERTY_HIGHLIGHT.CONFLICT
        : isModified
          ? PROPERTY_HIGHLIGHT.MODIFIED
          : undefined;

    return (
      <div
        key={prop.name}
        style={{
          background: bg,
          border: `1px solid ${isConflict ? '#ffa39e' : isModified ? '#ffe58f' : '#f0f0f0'}`,
          borderRadius: 4,
          padding: 8,
          marginBottom: 6,
        }}
      >
        <Row gutter={8} align="middle">
          <Col span={6}>
            <Text strong>{prop.name}</Text>
            {isConflict && <Tag color="red" style={{ marginLeft: 8 }}>conflict</Tag>}
            {!isConflict && isModified && <Tag color="orange" style={{ marginLeft: 8 }}>modified</Tag>}
            {resolved && <Tag color="green" style={{ marginLeft: 8 }}>{resolved.resolution}</Tag>}
          </Col>
          <Col span={4}>{renderValue(prop.ours_value)}</Col>
          <Col span={4}>{renderValue(prop.theirs_value)}</Col>
          <Col span={10}>
            {isConflict ? (
              <Space size={4}>
                <Button size="small" icon={<CheckOutlined />} onClick={() => setResolution(ot, prop, 'ours')}>Use Ours</Button>
                <Button size="small" icon={<SwapOutlined />} onClick={() => setResolution(ot, prop, 'theirs')}>Use Theirs</Button>
                <Button size="small" icon={<EditOutlined />} onClick={() => openManualEdit(ot, prop)}>Manual</Button>
              </Space>
            ) : (
              <Text type="secondary">-</Text>
            )}
          </Col>
        </Row>
      </div>
    );
  };

  return (
    <div data-testid="merge-diff-viewer" style={{ padding: 16 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} wrap>
        <Title level={3} style={{ margin: 0 }}>
          <BranchesOutlined /> 合并对比
        </Title>
        <Button
          type="primary"
          icon={<CheckOutlined />}
          onClick={handleConfirmMerge}
          loading={merging}
          disabled={!diff || remainingConflicts > 0}
        >
          Confirm Merge
        </Button>
      </Space>

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={12}>
          <Col xs={24} md={8}>
            <Text type="secondary">Base</Text>
            <Select
              style={{ width: '100%' }}
              value={baseVersion}
              onChange={setBaseVersion}
              options={versionOptions}
              placeholder="选择基础版本"
            />
          </Col>
          <Col xs={24} md={8}>
            <Text type="secondary">Ours</Text>
            <Select
              style={{ width: '100%' }}
              value={oursVersion}
              onChange={setOursVersion}
              options={versionOptions}
              placeholder="选择本地版本"
            />
          </Col>
          <Col xs={24} md={8}>
            <Text type="secondary">Theirs</Text>
            <Select
              style={{ width: '100%' }}
              value={theirsVersion}
              onChange={setTheirsVersion}
              options={versionOptions}
              placeholder="选择远端版本"
            />
          </Col>
        </Row>
      </Card>

      {diff && conflictCount > 0 && (
        <Alert
          type={remainingConflicts > 0 ? 'warning' : 'success'}
          showIcon
          icon={<ExclamationCircleOutlined />}
          title={
            <Space>
              <Text>共 {conflictCount} 个冲突，已解决 {resolvedCount}，剩余 {remainingConflicts}</Text>
            </Space>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      <Spin spinning={loading}>
        {!diff || diff.object_types.length === 0 ? (
          <Card><Empty description={!baseVersion || !oursVersion || !theirsVersion ? '请选择 Base / Ours / Theirs 版本' : '无差异'} /></Card>
        ) : (
          <Collapse
            accordion={false}
            defaultActiveKey={diff.object_types.map((o) => o.object_type)}
            items={diff.object_types.map((ot) => ({
              key: ot.object_type,
              label: (
                <Space>
                  <Text strong>{ot.object_type}</Text>
                  {ot.added && <Tag color="green">added</Tag>}
                  {ot.removed && <Tag color="red">removed</Tag>}
                  {ot.properties.filter((p) => p.has_conflict).length > 0 && (
                    <Tag color="red">
                      {ot.properties.filter((p) => p.has_conflict).length} conflict
                    </Tag>
                  )}
                  {ot.properties.filter((p) => !p.has_conflict && (p.changed_in_ours || p.changed_in_theirs)).length > 0 && (
                    <Tag color="orange">
                      {ot.properties.filter((p) => !p.has_conflict && (p.changed_in_ours || p.changed_in_theirs)).length} modified
                    </Tag>
                  )}
                </Space>
              ),
              children: (
                <div>
                  <Row gutter={8} style={{ marginBottom: 8, color: '#8c8c8c', fontSize: 12 }}>
                    <Col span={6}>属性</Col>
                    <Col span={4}>Ours</Col>
                    <Col span={4}>Theirs</Col>
                    <Col span={10}>操作</Col>
                  </Row>
                  {ot.properties.map((p) => renderPropertyRow(ot.object_type, p))}
                </div>
              ),
            }))}
          />
        )}
      </Spin>

      <Modal
        title={manualEdit ? `手动编辑 ${manualEdit.objectType}.${manualEdit.property.name}` : '手动编辑'}
        open={!!manualEdit}
        onOk={handleConfirmManual}
        onCancel={() => setManualEdit(null)}
        okText="应用"
        cancelText="取消"
      >
        {manualEdit && (
          <TextArea
            value={manualEdit.value}
            onChange={(e) => setManualEdit({ ...manualEdit, value: e.target.value })}
            autoFocus
            rows={4}
            placeholder="输入新的属性值（字符串/JSON/数字）"
          />
        )}
      </Modal>
    </div>
  );
}

export default MergeDiffViewer;
