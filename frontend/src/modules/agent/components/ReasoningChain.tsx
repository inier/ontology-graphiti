import { Collapse, Steps, Card, Empty, Tag } from 'antd';
import {
  BulbOutlined,
  FileSearchOutlined,
} from '@ant-design/icons';
import { useI18n } from '@/modules/shared/hooks/useI18n';

interface ReasoningStep {
  title?: string;
  description?: string;
  status?: 'wait' | 'process' | 'finish' | 'error';
}

interface ReasoningChainProps {
  reasoning: string;
  evidence: Record<string, unknown>[];
  steps?: ReasoningStep[];
}

export function ReasoningChain({ reasoning, evidence, steps }: ReasoningChainProps) {
  const { t } = useI18n('agent');

  if (!reasoning && (!evidence || evidence.length === 0) && (!steps || steps.length === 0)) {
    return (
      <Card title={t('reasoningChain')} size="small">
        <Empty description={t('noData')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  const collapseItems = [
    {
      key: 'reasoning',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <BulbOutlined />
          {t('reasoning')}
        </span>
      ),
      children: (
        <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, color: '#595959', lineHeight: 1.8 }}>
          {reasoning}
        </div>
      ),
    },
    {
      key: 'evidence',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileSearchOutlined />
          {t('evidence')} ({evidence?.length || 0})
        </span>
      ),
      children: evidence && evidence.length > 0 ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {evidence.map((item, index) => (
            <Tag key={index} color="blue">
              {typeof item === 'string' ? item : JSON.stringify(item)}
            </Tag>
          ))}
        </div>
      ) : (
        <Empty description={t('noData')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ),
    },
  ];

  return (
    <Card title={t('reasoningChain')} size="small">
      {steps && steps.length > 0 && (
        <Steps
          orientation="vertical"
          size="small"
          current={steps.findIndex((s) => s.status === 'process') !== -1 ? steps.findIndex((s) => s.status === 'process') : steps.length - 1}
          items={steps.map((step, index) => ({
            key: index,
            title: step.title || `${t('step')} ${index + 1}`,
            description: step.description,
            status: step.status || 'finish',
          }))}
          style={{ marginBottom: 16 }}
        />
      )}
      <Collapse items={collapseItems} defaultActiveKey={['reasoning']} size="small" />
    </Card>
  );
}
