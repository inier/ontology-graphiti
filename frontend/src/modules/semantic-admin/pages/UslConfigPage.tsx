/**
 * USL 规范配置页（5 子 Tab 容器）
 * 子 Tab：语义域列表 / 规范术语 / 层级结构 / 属性规范 / 高级约束
 */
import React, { useMemo } from 'react';
import { Alert, Space, Tabs, Typography } from 'antd';
import type { TabsProps } from 'antd';
import {
  DatabaseOutlined,
  TagsOutlined,
  PartitionOutlined,
  PropertySafetyOutlined,
  LockOutlined,
} from '@ant-design/icons';
import { useSemanticAdminStore, type UslSubTab } from '../store/useSemanticAdminStore';
import { DomainTable } from '../components/DomainTable';
import { TermTable } from '../components/TermTable';
import { HierarchyTree } from '../components/HierarchyTree';
import { PropertySpecTable } from '../components/PropertySpecTable';
import { DisjointPairTable } from '../components/DisjointPairTable';
import { CardinalityTable } from '../components/CardinalityTable';

const { Text } = Typography;

/** USL 配置页 5 子 Tab */
const USL_SUB_TAB_ITEMS: TabsProps['items'] = [
  {
    key: 'domains',
    label: (
      <span>
        <DatabaseOutlined style={{ marginRight: 6 }} />
        语义域列表
      </span>
    ),
  },
  {
    key: 'terms',
    label: (
      <span>
        <TagsOutlined style={{ marginRight: 6 }} />
        规范术语
      </span>
    ),
  },
  {
    key: 'hierarchy',
    label: (
      <span>
        <PartitionOutlined style={{ marginRight: 6 }} />
        层级结构
      </span>
    ),
  },
  {
    key: 'properties',
    label: (
      <span>
        <PropertySafetyOutlined style={{ marginRight: 6 }} />
        属性规范
      </span>
    ),
  },
  {
    key: 'constraints',
    label: (
      <span>
        <LockOutlined style={{ marginRight: 6 }} />
        高级约束
      </span>
    ),
  },
];

/** 高级约束 Tab 内容：不相交对 + 基数 上下两栏 */
function ConstraintsPanel() {
  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Typography.Title level={5} style={{ marginTop: 0, marginBottom: 12 }}>
          不相交约束对（Disjoint Pairs）
        </Typography.Title>
        <DisjointPairTable />
      </div>
      <div>
        <Typography.Title level={5} style={{ marginTop: 0, marginBottom: 12 }}>
          关系基数约束（Cardinality）
        </Typography.Title>
        <CardinalityTable />
      </div>
    </Space>
  );
}

export function UslConfigPage() {
  const currentDomain = useSemanticAdminStore((s) => s.currentDomain);
  const currentUslSubTab = useSemanticAdminStore((s) => s.currentUslSubTab);
  const setCurrentUslSubTab = useSemanticAdminStore((s) => s.setCurrentUslSubTab);

  /** 除「语义域」外的 4 个 Tab 都要求先选中语义域 */
  const needDomainContext: boolean = useMemo(
    () => ['terms', 'hierarchy', 'properties', 'constraints'].includes(currentUslSubTab),
    [currentUslSubTab],
  );

  /** 渲染 5 个子 Tab 对应的内容 */
  const renderSubTabContent = (tab: UslSubTab): React.ReactNode => {
    if (needDomainContext && !currentDomain) {
      return (
        <Alert
          type="info"
          showIcon
          message="请先在「语义域列表」Tab 中选中一个语义域"
          description={
            <Text type="secondary">
              术语、层级、属性、约束都从属于特定语义域；点击「语义域列表」表格行的「选择」按钮建立上下文后再切回本 Tab。
            </Text>
          }
        />
      );
    }
    switch (tab) {
      case 'domains':
        return <DomainTable />;
      case 'terms':
        return <TermTable />;
      case 'hierarchy':
        return <HierarchyTree />;
      case 'properties':
        return <PropertySpecTable />;
      case 'constraints':
        return <ConstraintsPanel />;
      default:
        return null;
    }
  };

  return (
    <div>
      {currentDomain && (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 12 }}
          message={
            <Space>
              <Text strong>当前语义域：</Text>
              <Text code>{currentDomain.code}</Text>
              <Text>{currentDomain.display_name}</Text>
              {typeof currentDomain.term_count === 'number' && (
                <Text type="secondary">
                  共 {currentDomain.term_count} 条术语
                </Text>
              )}
            </Space>
          }
        />
      )}
      <Tabs
        activeKey={currentUslSubTab}
        onChange={(k) => setCurrentUslSubTab(k as UslSubTab)}
        items={USL_SUB_TAB_ITEMS}
        destroyInactiveTabPane={false}
      >
        {/* Tabs 组件使用 items 模式，但为了每个 tab 的内容能正确拿到 domain 上下文，我们手动把所有 key 的内容都渲染在一个受控 Tab 里 */}
      </Tabs>
      {/* 由于我们用了受控的 activeKey + onChange，这里手动挂内容区（避免 items 的 children 写法嵌套过深）*/}
      <div style={{ marginTop: 8 }}>
        {renderSubTabContent(currentUslSubTab)}
      </div>
    </div>
  );
}
