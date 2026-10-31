/**
 * OntologyRelationsPage —— 本体「关系与派生」工作面
 *
 * 收敛此前只在 barrel 里 `export`、却没有任何路由能挂载的四个组件
 * （继承图 / Mixin / 计算属性 / 物化任务），消除「有实现无入口」的断链：
 *
 *   Tab 1 继承图   → <InheritanceGraph />      /api/ontology/inheritance/*
 *   Tab 2 Mixin    → <MixinConfig />           /api/ontology/inheritance/mixins*
 *   Tab 3 计算属性 → <ComputedPropertyList />  /api/ontology/computed/properties*
 *   Tab 4 物化任务 → <MaterializationJobsPanel /> /api/ontology/computed/properties/{id}/jobs
 *
 * 四个 Tab 彼此不共享状态，各自按需拉取；懒挂载（`destroyOnHidden`）避免
 * 一进页面就打满 N 个请求。
 */
import { useState } from 'react';
import { Card, Tabs } from 'antd';
import { ApartmentOutlined, AppstoreOutlined, FunctionOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { PageHeader } from '@/modules/shared/components/PageHeader';
import { InheritanceGraph } from '../components/InheritanceGraph';
import { MixinConfig } from '../components/MixinConfig';
import { ComputedPropertyList } from '../components/ComputedPropertyList';
import { MaterializationJobsPanel } from '../components/MaterializationJobsPanel';

type RelationsTab = 'inheritance' | 'mixin' | 'computed' | 'materialization';

export function OntologyRelationsPage() {
  const [activeKey, setActiveKey] = useState<RelationsTab>('inheritance');

  return (
    <div style={{ padding: 16 }}>
      <PageHeader title="本体关系与派生" />

      <Card styles={{ body: { paddingTop: 0 } }}>
        <Tabs
          activeKey={activeKey}
          onChange={(k) => setActiveKey(k as RelationsTab)}
          destroyOnHidden
          items={[
            {
              key: 'inheritance',
              label: (
                <span>
                  <ApartmentOutlined /> 继承图
                </span>
              ),
              children: <InheritanceGraph />,
            },
            {
              key: 'mixin',
              label: (
                <span>
                  <AppstoreOutlined /> Mixin
                </span>
              ),
              children: <MixinConfig />,
            },
            {
              key: 'computed',
              label: (
                <span>
                  <FunctionOutlined /> 计算属性
                </span>
              ),
              children: <ComputedPropertyList />,
            },
            {
              key: 'materialization',
              label: (
                <span>
                  <ThunderboltOutlined /> 物化任务
                </span>
              ),
              children: <MaterializationJobsPanel />,
            },
          ]}
        />
      </Card>
    </div>
  );
}

export default OntologyRelationsPage;
