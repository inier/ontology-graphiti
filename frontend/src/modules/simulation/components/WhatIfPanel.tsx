import { useState } from 'react';
import { Form, InputNumber, Button, Card, Table, Tag, Space, Typography, message } from 'antd';
import { ExperimentOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

interface ParamVariation {
  key: string;
  value: number;
}

interface SensitivityRow {
  parameter: string;
  delta: number;
  impact: number;
  direction: string;
}

interface WhatIfPanelProps {
  sandboxId?: string;
  scenarioId?: string;
}

function WhatIfPanel({ sandboxId, scenarioId }: WhatIfPanelProps) {
  const { t } = useI18n('simulation');
  const [params, setParams] = useState<ParamVariation[]>([{ key: '', value: 0 }]);
  const [loading, setLoading] = useState(false);
  const [sensitivityData, setSensitivityData] = useState<SensitivityRow[]>([]);

  const handleAddParam = () => {
    setParams(prev => [...prev, { key: '', value: 0 }]);
  };

  const handleRemoveParam = (index: number) => {
    setParams(prev => prev.filter((_, i) => i !== index));
  };

  const handleParamChange = (index: number, field: keyof ParamVariation, value: string | number) => {
    setParams(prev => prev.map((p, i) => (i === index ? { ...p, [field]: value } : p)));
  };

  const handleRunWhatIf = async () => {
    const validParams = params.filter(p => p.key.trim());
    if (validParams.length === 0) {
      message.warning(t('whatif.noParams', 'Add at least one parameter'));
      return;
    }

    setLoading(true);
    try {
      const payload: Record<string, unknown> = {
        param_variations: validParams.map(p => ({ [p.key]: p.value })),
      };
      if (sandboxId) payload.sandbox_id = sandboxId;
      if (scenarioId) payload.scenario_id = scenarioId;

      const data = await apiClient.post<{
        sensitivity_analysis: Record<string, Array<{ delta: number; impact: number; direction: string }>>;
      }>('/api/simulation/what-if', payload);

      if (data.sensitivity_analysis) {
        const rows: SensitivityRow[] = [];
        Object.entries(data.sensitivity_analysis).forEach(([param, variations]) => {
          (variations as Array<{ delta: number; impact: number; direction: string }>).forEach(v => {
            rows.push({
              parameter: param,
              delta: v.delta,
              impact: v.impact,
              direction: v.direction,
            });
          });
        });
        setSensitivityData(rows);
      }
      message.success(t('whatif.completed', 'What-if analysis completed'));
    } catch (e) {
      message.error(`${t('whatif.failed', 'Analysis failed')}: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: t('whatif.parameter', 'Parameter'),
      dataIndex: 'parameter',
      key: 'parameter',
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: t('whatif.delta', 'Delta'),
      dataIndex: 'delta',
      key: 'delta',
      render: (v: number) => (
        <Text style={{ color: v >= 0 ? '#52c41a' : '#ff4d4f' }}>
          {v >= 0 ? '+' : ''}{v.toFixed(4)}
        </Text>
      ),
    },
    {
      title: t('whatif.impact', 'Impact'),
      dataIndex: 'impact',
      key: 'impact',
      render: (v: number) => (
        <Text style={{ color: Math.abs(v) > 0.5 ? '#ff4d4f' : Math.abs(v) > 0.2 ? '#faad14' : '#52c41a' }}>
          {v.toFixed(4)}
        </Text>
      ),
    },
    {
      title: t('whatif.direction', 'Direction'),
      dataIndex: 'direction',
      key: 'direction',
      render: (v: string) => (
        <Tag color={v === 'positive' ? 'green' : v === 'negative' ? 'red' : 'default'}>{v}</Tag>
      ),
    },
  ];

  return (
    <Card
      title={t('whatif.title', 'What-If Analysis')}
      size="small"
      extra={
        <Button
          type="primary"
          icon={<ExperimentOutlined />}
          onClick={handleRunWhatIf}
          loading={loading}
        >
          {t('whatif.run', 'Run What-If')}
        </Button>
      }
    >
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Card type="inner" title={t('whatif.parameters', 'Parameter Variations')} size="small">
          {params.map((param, idx) => (
            <Space key={idx} style={{ marginBottom: 8 }} align="baseline">
              <Form.Item label={t('whatif.key', 'Key')} style={{ marginBottom: 0 }}>
                <input
                  value={param.key}
                  onChange={e => handleParamChange(idx, 'key', e.target.value)}
                  placeholder="parameter_name"
                  style={{ width: 160, padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 6 }}
                />
              </Form.Item>
              <Form.Item label={t('whatif.value', 'Value')} style={{ marginBottom: 0 }}>
                <InputNumber
                  value={param.value}
                  onChange={v => handleParamChange(idx, 'value', v ?? 0)}
                  style={{ width: 120 }}
                />
              </Form.Item>
              <Button
                danger
                size="small"
                onClick={() => handleRemoveParam(idx)}
                disabled={params.length <= 1}
              >
                {t('whatif.remove', 'Remove')}
              </Button>
            </Space>
          ))}
          <Button type="dashed" onClick={handleAddParam} style={{ marginTop: 8 }}>
            {t('whatif.addParam', 'Add Parameter')}
          </Button>
        </Card>

        {sensitivityData.length > 0 && (
          <Card type="inner" title={t('whatif.sensitivity', 'Sensitivity Analysis')} size="small">
            <Table
              dataSource={sensitivityData}
              columns={columns}
              rowKey={(r) => `${r.parameter}-${r.delta}`}
              size="small"
              pagination={false}
            />
          </Card>
        )}
      </Space>
    </Card>
  );
}

export default WhatIfPanel;
