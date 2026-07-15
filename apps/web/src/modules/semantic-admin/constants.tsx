/**
 * semantic-admin 模块常量与共享配置（避免 fast-refresh only-export-components 限制）
 */
import type { TabsProps } from 'antd';
import {
  ApartmentOutlined,
  ThunderboltOutlined,
  SafetyCertificateOutlined,
  BarChartOutlined,
  DashboardOutlined,
  AuditOutlined,
} from '@ant-design/icons';
import type { AdminTopTab } from './store/useSemanticAdminStore';
import React from 'react';

export const TOP_TAB_TO_PATH: Record<AdminTopTab, string> = {
  usl: '/semantic-admin/usl',
  pipeline: '/semantic-admin/pipeline',
  candidates: '/semantic-admin/candidates',
  quality: '/semantic-admin/quality',
  dashboard: '/semantic-admin/dashboard',
  approvals: '/semantic-admin/approvals',
};

export const PATH_TO_TOP_TAB: Record<string, AdminTopTab> = {
  '/semantic-admin/usl': 'usl',
  '/semantic-admin/pipeline': 'pipeline',
  '/semantic-admin/candidates': 'candidates',
  '/semantic-admin/quality': 'quality',
  '/semantic-admin/dashboard': 'dashboard',
  '/semantic-admin/approvals': 'approvals',
};

/** 4 个顶层 Tab 条目（供各子页渲染共用） */
export const SEMANTIC_ADMIN_TAB_ITEMS: TabsProps['items'] = [
  {
    key: 'usl',
    label: (
      <span>
        <ApartmentOutlined style={{ marginRight: 6 }} />
        USL 规范配置
      </span>
    ),
  },
  {
    key: 'pipeline',
    label: (
      <span>
        <ThunderboltOutlined style={{ marginRight: 6 }} />
        OL 流水线 <span style={{ color: '#999', fontSize: 12 }}>(Iter 2)</span>
      </span>
    ),
  },
  {
    key: 'candidates',
    label: (
      <span>
        <SafetyCertificateOutlined style={{ marginRight: 6 }} />
        候选审核台 <span style={{ color: '#999', fontSize: 12 }}>(Iter 3)</span>
      </span>
    ),
  },
  {
    key: 'quality',
    label: (
      <span>
        <BarChartOutlined style={{ marginRight: 6 }} />
        质量面板 <span style={{ color: '#999', fontSize: 12 }}>(Iter 4)</span>
      </span>
    ),
  },
  {
    key: 'dashboard',
    label: (
      <span>
        <DashboardOutlined style={{ marginRight: 6 }} />
        治理仪表盘
      </span>
    ),
  },
  {
    key: 'approvals',
    label: (
      <span>
        <AuditOutlined style={{ marginRight: 6 }} />
        审批工作台 <span style={{ color: '#999', fontSize: 12 }}>(2 级审批)</span>
      </span>
    ),
  },
];
