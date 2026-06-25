/**
 * HealthDashboard 页面 —— 数据健康报告页面（FR-031 / T346）
 *
 * L5 页面：聚合 HealthRuleEditor + HealthDashboard 组件
 * 左侧规则列表 + 顶部 KPI + 主区域报告可视化
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, Button, Space, Tabs, Empty, Spin, Drawer, Statistic, Tag, message, Typography, List, Divider, Alert,
} from 'antd';
import {
  ReloadOutlined, PlusOutlined, ThunderboltOutlined, CheckCircleTwoTone, CloseCircleTwoTone, WarningTwoTone, MinusCircleTwoTone,
} from '@ant-design/icons';
import { HealthDashboard } from '../components/HealthDashboard';
import { HealthRuleEditor } from '../components/HealthRuleEditor';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { ReactNode } from 'react';
import { AdvancedTable } from '@/modules/shared';

const { Title, Text } = Typography;

export interface HealthDashboardPageProps {
  workspaceId?: string;
}

type RuleStatus = 'PASS' | 'FAIL' | 'WARN' | 'SKIP';

interface HealthRule {
  rule_id: string;
  name: string;
  description?: string;
  object_type?: string;
  severity?: string;
  status: RuleStatus;
  failure_count: number;
  last_checked_at?: string;
}

export function HealthDashboardPage({ workspaceId }: HealthDashboardPageProps) {
  const { t } = useI18n();
  void t;
  const [rules, setRules] = useState<HealthRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [selectedRuleId, setSelectedRuleId] = useState<string | undefined>();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ rules: HealthRule[] }>('/api/ontology/health/rules');
      setRules(data.rules || []);
    } catch (e) {
      message.error(`加载失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchRules(); }, [fetchRules]);

  const onRunScan = useCallback(async () => {
    setScanning(true);
    try {
      await apiClient.post('/api/ontology/health/scan', { workspace_id: workspaceId });
      message.success('扫描已启动');
      await fetchRules();
    } catch (e) {
      message.error(`扫描失败: ${(e as Error).message}`);
    } finally {
      setScanning(false);
    }
  }, [fetchRules, workspaceId]);

  const totals = useMemo(() => {
    const total = rules.length;
    const pass = rules.filter((r) => r.status === 'PASS').length;
    const fail = rules.filter((r) => r.status === 'FAIL').length;
    const warn = rules.filter((r) => r.status === 'WARN').length;
    const rate = total > 0 ? Math.round((pass / total) * 100) : 0;
    return { total, pass, fail, warn, rate };
  }, [rules]);

  const lastScanAt = useMemo(() => {
    const items = rules.filter((r) => r.last_checked_at);
    if (items.length === 0) return '-';
    return items.map((r) => r.last_checked_at).sort().slice(-1)[0];
  }, [rules]);

  return (
    <div>
      <Card
        title={
          <Space>
            <Title level={4} style={{ margin: 0 }}>数据健康看板</Title>
            <Tag color="blue">{workspaceId || 'default'}</Tag>
          </Space>
        }
        extra={
          <Space>
            <Button icon={<PlusOutlined />} onClick={() => setEditorOpen(true)}>新建规则</Button>
            <Button type="primary" icon={<ThunderboltOutlined />} loading={scanning} onClick={onRunScan}>
              运行扫描
            </Button>
          </Space>
        }
      >
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}><Card><Statistic title="总规则数" value={totals.total} prefix={<ThunderboltOutlined />} /></Card></Col>
          <Col span={6}><Card><Statistic title="通过率" value={totals.rate} suffix="%" styles={{ content: { color: '#3f8600' } }} /></Card></Col>
          <Col span={6}><Card><Statistic title="失败规则" value={totals.fail} styles={{ content: { color: '#cf1322' } }} prefix={<CloseCircleTwoTone twoToneColor="#cf1322" />} /></Card></Col>
          <Col span={6}><Card><Statistic title="最后扫描" value={lastScanAt} styles={{ content: { fontSize: 14 } }} /></Card></Col>
        </Row>
        <Tabs
          defaultActiveKey="rules"
          items={[
            {
              key: 'rules',
              label: '规则列表',
              children: (
                <Spin spinning={loading}>
                  {rules.length === 0 ? (
                    <Empty description="暂无规则" />
                  ) : (
                    <AdvancedTable
                      rowKey="rule_id"
                      dataSource={rules}
                      pagination={false}
                      onRow={(r) => ({
                        onClick: () => { setSelectedRuleId(r.rule_id); setDrawerOpen(true); },
                        style: { cursor: 'pointer' },
                      })}
                      columns={[
                        { title: 'ID', dataIndex: 'rule_id', width: 120 },
                        { title: 'Name', dataIndex: 'name' },
                        { title: 'Object Type', dataIndex: 'object_type', width: 140 },
                        { title: 'Severity', dataIndex: 'severity', width: 110, render: (v?: string) => v ? <Tag>{v}</Tag> : '-' },
                        {
                          title: 'Status', dataIndex: 'status', width: 110,
                          render: (s: RuleStatus) => {
                            const map: Record<RuleStatus, { icon: ReactNode; color: string }> = {
                              PASS: { icon: <CheckCircleTwoTone twoToneColor="#52c41a" />, color: 'success' },
                              FAIL: { icon: <CloseCircleTwoTone twoToneColor="#f5222d" />, color: 'error' },
                              WARN: { icon: <WarningTwoTone twoToneColor="#faad14" />, color: 'warning' },
                              SKIP: { icon: <MinusCircleTwoTone />, color: 'default' },
                            };
                            return <Space>{map[s].icon}<Text>{s}</Text></Space>;
                          },
                        },
                        { title: '失败数', dataIndex: 'failure_count', width: 100 },
                        { title: '最近检查', dataIndex: 'last_checked_at', width: 180 },
                      ]}
                    />
                  )}
                </Spin>
              ),
            },
            {
              key: 'dashboard',
              label: '可视化',
              children: <HealthDashboard workspaceId={workspaceId} />,
            },
          ]}
        />
      </Card>

      <Drawer
        title={selectedRuleId ? `规则详情: ${selectedRuleId}` : '规则详情'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={720}
      >
        {selectedRuleId && <HealthRuleEditor workspaceId={workspaceId} ruleId={selectedRuleId} />}
      </Drawer>

      <Drawer
        title="新建健康规则"
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        width={960}
      >
        <HealthRuleEditor
          workspaceId={workspaceId}
          onSaved={(id) => { setEditorOpen(false); setSelectedRuleId(id); fetchRules(); }}
        />
      </Drawer>

      {rules.length === 0 && !loading && (
        <Alert
          style={{ marginTop: 16 }}
          type="info"
          showIcon
          message="数据健康规则说明"
          description={
            <List
              size="small"
              dataSource={[
                '点击"新建规则"创建第一个数据健康规则',
                '点击"运行扫描"立即对所有规则触发扫描',
                '点击表格行查看 / 编辑已有规则',
              ]}
              renderItem={(it) => <List.Item>{it}</List.Item>}
            />
          }
        />
      )}
      <Divider />
    </div>
  );
}

export default HealthDashboardPage;
