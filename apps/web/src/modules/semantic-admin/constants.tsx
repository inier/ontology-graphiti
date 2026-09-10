/**
 * semantic-admin 模块常量与共享配置（避免 fast-refresh only-export-components 限制）
 *
 * 注意：SEMANTIC_ADMIN_TAB_ITEMS 改为函数 getSemanticAdminTabItems(t)，以便
 * Tab 标签走 i18n（AGENTS.md 规则：前端国际化使用中文作为 i18n key）。
 * 同时保留 SEMANTIC_ADMIN_TAB_ITEMS_KEYS 供测试与路径映射对齐校验。
 */
import type { TabsProps } from 'antd';
import type { TFunction } from 'i18next';
import {
  ApartmentOutlined,
  ThunderboltOutlined,
  SafetyCertificateOutlined,
  BarChartOutlined,
  DashboardOutlined,
  AuditOutlined,
  CloudSyncOutlined,
} from '@ant-design/icons';
import type { AdminTopTab } from './store/useSemanticAdminStore';
import React from 'react';

export const TOP_TAB_TO_PATH: Record<AdminTopTab, string> = {
  assets: '/semantic-admin/assets',
  usl: '/semantic-admin/usl',
  pipeline: '/semantic-admin/pipeline',
  candidates: '/semantic-admin/candidates',
  quality: '/semantic-admin/quality',
  dashboard: '/semantic-admin/dashboard',
  approvals: '/semantic-admin/approvals',
};

export const PATH_TO_TOP_TAB: Record<string, AdminTopTab> = {
  '/semantic-admin/assets': 'assets',
  '/semantic-admin/usl': 'usl',
  '/semantic-admin/usl-ontologies': 'usl',
  '/semantic-admin/pipeline': 'pipeline',
  '/semantic-admin/candidates': 'candidates',
  '/semantic-admin/quality': 'quality',
  '/semantic-admin/dashboard': 'dashboard',
  '/semantic-admin/approvals': 'approvals',
};

/** 顶层 Tab key 列表（供测试与静态校验使用，不依赖 t） */
export const SEMANTIC_ADMIN_TAB_ITEMS_KEYS: AdminTopTab[] = [
  'assets',
  'usl',
  'pipeline',
  'candidates',
  'quality',
  'dashboard',
  'approvals',
];

/**
 * 构造 6 个顶层 Tab 条目（供各子页渲染共用）。
 *
 * 使用方式：
 *   const { t } = useI18n();
 *   const items = useMemo(() => getSemanticAdminTabItems(t), [t]);
 *   <Tabs items={items} ... />
 *
 * 为什么是函数而非常量：Tab label 需走 i18n，必须接收 t 函数；
 * 调用方应使用 useMemo([t]) 包裹以避免每次渲染重建。
 */
export function getSemanticAdminTabItems(t: TFunction): NonNullable<TabsProps['items']> {
  return [
    {
      key: 'assets',
      label: (
        <span>
          <CloudSyncOutlined style={{ marginRight: 6 }} />
          {t('语义资产 Pipeline')}
        </span>
      ),
    },
    {
      key: 'usl',
      label: (
        <span>
          <ApartmentOutlined style={{ marginRight: 6 }} />
          {t('USL 规范配置')}
        </span>
      ),
    },
    {
      key: 'pipeline',
      label: (
        <span>
          <ThunderboltOutlined style={{ marginRight: 6 }} />
          {t('OL 流水线')}
        </span>
      ),
    },
    {
      key: 'candidates',
      label: (
        <span>
          <SafetyCertificateOutlined style={{ marginRight: 6 }} />
          {t('候选审核台')}
        </span>
      ),
    },
    {
      key: 'quality',
      label: (
        <span>
          <BarChartOutlined style={{ marginRight: 6 }} />
          {t('质量面板')}
        </span>
      ),
    },
    {
      key: 'dashboard',
      label: (
        <span>
          <DashboardOutlined style={{ marginRight: 6 }} />
          {t('治理仪表盘')}
        </span>
      ),
    },
    {
      key: 'approvals',
      label: (
        <span>
          <AuditOutlined style={{ marginRight: 6 }} />
          {t('审批工作台')}
        </span>
      ),
    },
  ];
}
