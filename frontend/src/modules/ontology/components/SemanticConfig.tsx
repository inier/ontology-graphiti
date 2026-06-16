import { useState, useEffect } from 'react';
import { Table, Input, Button, Card, Space, Typography, Popconfirm, message } from 'antd';
import { PlusOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';

const { Text } = Typography;

interface SynonymEntry {
  key: string;
  canonical: string;
  synonyms: string[];
}

interface ExpansionRuleEntry {
  key: number;
  pattern: string;
  expansion: string[];
}

export default function SemanticConfig() {
  const [synonyms, setSynonyms] = useState<SynonymEntry[]>([]);
  const [expansionRules, setExpansionRules] = useState<ExpansionRuleEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [synCanonical, setSynCanonical] = useState('');
  const [synValue, setSynValue] = useState('');
  const [rulePattern, setRulePattern] = useState('');
  const [ruleExpansion, setRuleExpansion] = useState('');

  useEffect(() => {
    loadSynonyms();
    loadExpansionRules();
  }, []);

  const loadSynonyms = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ synonyms: Record<string, string[]> }>('/api/semantic/synonyms');
      const entries = Object.entries(data.synonyms || {}).map(([canonical, syns]) => ({
        key: canonical,
        canonical,
        synonyms: syns,
      }));
      setSynonyms(entries);
    } catch {
      setSynonyms([]);
    } finally {
      setLoading(false);
    }
  };

  const loadExpansionRules = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ rules: Array<{ pattern: string; expansion: string[] }> }>('/api/semantic/expansion-rules');
      setExpansionRules(
        (data.rules || []).map((r, i) => ({
          key: i,
          pattern: r.pattern,
          expansion: r.expansion,
        })),
      );
    } catch {
      setExpansionRules([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAddSynonym = async () => {
    if (!synCanonical.trim() || !synValue.trim()) {
      message.warning('Both canonical and synonym are required');
      return;
    }
    try {
      await apiClient.post('/api/semantic/synonyms', {
        canonical: synCanonical,
        synonym: synValue,
      });
      message.success('Synonym added');
      setSynCanonical('');
      setSynValue('');
      loadSynonyms();
    } catch (e) {
      message.error(`Add synonym failed: ${(e as Error).message}`);
    }
  };

  const handleAddExpansionRule = async () => {
    if (!rulePattern.trim() || !ruleExpansion.trim()) {
      message.warning('Both pattern and expansion are required');
      return;
    }
    try {
      await apiClient.post('/api/semantic/expansion-rules', {
        pattern: rulePattern,
        expansion: ruleExpansion,
      });
      message.success('Expansion rule added');
      setRulePattern('');
      setRuleExpansion('');
      loadExpansionRules();
    } catch (e) {
      message.error(`Add rule failed: ${(e as Error).message}`);
    }
  };

  const handleRemoveSynonym = async (canonical: string, synonym: string) => {
    try {
      await apiClient.delete(`/api/semantic/synonyms/${encodeURIComponent(canonical)}/${encodeURIComponent(synonym)}`);
      message.success('Synonym removed');
      loadSynonyms();
    } catch (e) {
      message.error(`Remove failed: ${(e as Error).message}`);
    }
  };

  const handleRemoveExpansionRule = async (pattern: string) => {
    try {
      await apiClient.delete(`/api/semantic/expansion-rules/${encodeURIComponent(pattern)}`);
      message.success('Rule removed');
      loadExpansionRules();
    } catch (e) {
      message.error(`Remove failed: ${(e as Error).message}`);
    }
  };

  const synonymColumns = [
    {
      title: 'Canonical',
      dataIndex: 'canonical',
      key: 'canonical',
      width: 200,
    },
    {
      title: 'Synonyms',
      dataIndex: 'synonyms',
      key: 'synonyms',
      render: (syns: string[], record: SynonymEntry) => (
        <Space size={4} wrap>
          {syns.map((s) => (
            <span key={s} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <Text style={{ background: '#f0f0f0', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>{s}</Text>
              <Popconfirm description={`Remove "${s}" from "${record.canonical}"?`} onConfirm={() => handleRemoveSynonym(record.canonical, s)}>
                <DeleteOutlined style={{ color: '#ff4d4f', cursor: 'pointer', fontSize: 11 }} />
              </Popconfirm>
            </span>
          ))}
        </Space>
      ),
    },
  ];

  const expansionColumns = [
    {
      title: 'Pattern',
      dataIndex: 'pattern',
      key: 'pattern',
      width: 250,
    },
    {
      title: 'Expansion',
      dataIndex: 'expansion',
      key: 'expansion',
      render: (exp: string[], record: ExpansionRuleEntry) => (
        <Space size={4} wrap>
          {exp.map((e) => (
            <Text key={e} style={{ background: '#e6f7ff', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>{e}</Text>
          ))}
          <Popconfirm description={`Remove rule "${record.pattern}"?`} onConfirm={() => handleRemoveExpansionRule(record.pattern)}>
            <DeleteOutlined style={{ color: '#ff4d4f', cursor: 'pointer', fontSize: 11 }} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Space orientation="vertical" style={{ width: '100%' }} size="middle">
      <Card
        title="Synonym / Near-synonym Mapping"
        size="small"
        extra={
          <Button size="small" icon={<ReloadOutlined />} onClick={loadSynonyms}>
            Refresh
          </Button>
        }
      >
        <Space style={{ marginBottom: 16 }} wrap>
          <Input
            placeholder="Canonical term"
            value={synCanonical}
            onChange={(e) => setSynCanonical(e.target.value)}
            style={{ width: 180 }}
          />
          <Input
            placeholder="Synonym"
            value={synValue}
            onChange={(e) => setSynValue(e.target.value)}
            style={{ width: 180 }}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAddSynonym}>
            Add
          </Button>
        </Space>
        <Table
          dataSource={synonyms}
          columns={synonymColumns}
          rowKey="key"
          size="small"
          loading={loading}
          pagination={false}
        />
      </Card>

      <Card
        title="Expansion Rules"
        size="small"
        extra={
          <Button size="small" icon={<ReloadOutlined />} onClick={loadExpansionRules}>
            Refresh
          </Button>
        }
      >
        <Space style={{ marginBottom: 16 }} wrap>
          <Input
            placeholder="Pattern"
            value={rulePattern}
            onChange={(e) => setRulePattern(e.target.value)}
            style={{ width: 220 }}
          />
          <Input
            placeholder="Expansion"
            value={ruleExpansion}
            onChange={(e) => setRuleExpansion(e.target.value)}
            style={{ width: 220 }}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAddExpansionRule}>
            Add
          </Button>
        </Space>
        <Table
          dataSource={expansionRules}
          columns={expansionColumns}
          rowKey="key"
          size="small"
          loading={loading}
          pagination={false}
        />
      </Card>
    </Space>
  );
}
