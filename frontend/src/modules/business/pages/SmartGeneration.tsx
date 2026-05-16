import { Tabs } from 'antd';
import { ExperimentOutlined, DatabaseOutlined } from '@ant-design/icons';
import { IngestPanel } from '../../ingest';

export function SmartGeneration() {
  const tabItems = [
    {
      key: 'ingest',
      label: (
        <span>
          <DatabaseOutlined style={{ marginRight: 4 }} />
          数据摄入
        </span>
      ),
      children: <IngestPanel />,
    },
    {
      key: 'extraction',
      label: (
        <span>
          <ExperimentOutlined style={{ marginRight: 4 }} />
          抽取记录
        </span>
      ),
      children: <ExtractionRecords />,
    },
  ];

  return (
    <Tabs
      defaultActiveKey="ingest"
      items={tabItems}
    />
  );
}

function ExtractionRecords() {
  return (
    <div style={{ padding: '16px 0' }}>
      <div style={{ marginBottom: 16, color: '#8c8c8c', fontSize: 13 }}>
        展示当前本体版本定义的自动抽取过程，以及每一步的输入和输出。
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {[
          { title: '文档预处理', input: '原始文档', output: '结构化文本段落', color: '#1890ff' },
          { title: '实体识别与抽取', input: '结构化文本', output: '实体列表及属性', color: '#52c41a' },
          { title: '关系构建', input: '实体列表', output: '实体关系三元组', color: '#722ed1' },
          { title: '知识入库', input: '实体关系三元组', output: '知识图谱更新', color: '#fa8c16' },
        ].map((step, index) => (
          <div
            key={index}
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '12px 16px',
              background: '#fafafa',
              borderRadius: 8,
              borderLeft: `3px solid ${step.color}`,
            }}
          >
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: step.color, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, marginRight: 16, flexShrink: 0 }}>
              {index + 1}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{step.title}</div>
              <div style={{ fontSize: 12, color: '#8c8c8c' }}>
                输入：{step.input} → 输出：{step.output}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
