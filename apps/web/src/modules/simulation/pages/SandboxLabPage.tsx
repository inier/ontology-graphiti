/**
 * SandboxLabPage —— 仿真推演工作台
 *
 * 把三块此前「有后端契约、无前端入口」的能力收在同一页：
 *  1. 沙箱：`/api/simulation/sandbox/*`（创建 / 运行 / 停止 / 结果 / 销毁）
 *  2. 假设推演：`/api/simulation/what-if`（参数变体 → 指标敏感度）
 *  3. 反馈闭环：`/api/feedback/{analysis,aggregate,close-loop}`（执行结果回写与教训沉淀）
 *
 * 三者是同一条链路的三段：在沙箱里试 → 对关键参数做 what-if → 把结论回写成反馈/记忆。
 * 拆成三个页面会让用户丢掉这条动线，所以用页签聚合。
 */
import { Card, Tabs } from 'antd';
import { ExperimentOutlined } from '@ant-design/icons';
import SandboxManager from '../pages/SandboxManager';
import WhatIfPanel from '../components/WhatIfPanel';
import FeedbackPanel from '../components/FeedbackPanel';
import { useOntologyStore } from '@/modules/ontology/stores/ontologyStore';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export function SandboxLabPage() {
  const { t } = useI18n('simulation');
  const currentOntology = useOntologyStore((state) => state.currentOntology);

  return (
    <Card
      title={
        <span>
          <ExperimentOutlined style={{ marginRight: 8 }} />
          {t('仿真推演工作台')}
        </span>
      }
    >
      <Tabs
        defaultActiveKey="sandbox"
        items={[
          {
            key: 'sandbox',
            label: t('沙箱'),
            children: <SandboxManager />,
          },
          {
            key: 'whatif',
            label: t('假设推演'),
            children: <WhatIfPanel defaultTargetObjectType="" />,
          },
          {
            key: 'feedback',
            label: t('反馈闭环'),
            children: (
              <FeedbackPanel ontologyId={currentOntology?.ontology_id} />
            ),
          },
        ]}
      />
    </Card>
  );
}

export default SandboxLabPage;
