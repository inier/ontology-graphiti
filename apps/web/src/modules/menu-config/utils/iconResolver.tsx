/**
 * 统一的菜单图标解析器，AdminLayout / MenuConfigPage / ProLayout 共用。
 * 架构决策：不再在每个组件重复 ICON_NAME_MAP，单一来源保证一致性。
 */
import React from 'react';
import {
  AppstoreOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  LinkOutlined,
  GlobalOutlined,
  SettingOutlined,
  MonitorOutlined,
  ToolOutlined,
  ApiOutlined,
  CodeOutlined,
  BookOutlined,
  BlockOutlined,
  FolderOutlined,
  FileOutlined,
  ThunderboltOutlined,
  RobotOutlined,
  TeamOutlined,
  SafetyOutlined,
  ApartmentOutlined,
  BranchesOutlined,
  NodeIndexOutlined,
  FundOutlined,
  FileProtectOutlined,
  UnorderedListOutlined,
  ExperimentOutlined,
  PartitionOutlined,
  HistoryOutlined,
  FileTextOutlined,
  AuditOutlined,
  UserOutlined,
  CompassOutlined,
  MessageOutlined,
} from '@ant-design/icons';

/* 统一的图标名 → 组件映射 */
const ICON_NAME_MAP: Record<string, React.ReactNode> = {
  AppstoreOutlined: <AppstoreOutlined />,
  CloudServerOutlined: <CloudServerOutlined />,
  DatabaseOutlined: <DatabaseOutlined />,
  LinkOutlined: <LinkOutlined />,
  GlobalOutlined: <GlobalOutlined />,
  SettingOutlined: <SettingOutlined />,
  MonitorOutlined: <MonitorOutlined />,
  ToolOutlined: <ToolOutlined />,
  ApiOutlined: <ApiOutlined />,
  CodeOutlined: <CodeOutlined />,
  BookOutlined: <BookOutlined />,
  BlockOutlined: <BlockOutlined />,
  FolderOutlined: <FolderOutlined />,
  FileOutlined: <FileOutlined />,
  ThunderboltOutlined: <ThunderboltOutlined />,
  RobotOutlined: <RobotOutlined />,
  TeamOutlined: <TeamOutlined />,
  SafetyOutlined: <SafetyOutlined />,
  ApartmentOutlined: <ApartmentOutlined />,
  BranchesOutlined: <BranchesOutlined />,
  NodeIndexOutlined: <NodeIndexOutlined />,
  FundOutlined: <FundOutlined />,
  FileProtectOutlined: <FileProtectOutlined />,
  UnorderedListOutlined: <UnorderedListOutlined />,
  ExperimentOutlined: <ExperimentOutlined />,
  PartitionOutlined: <PartitionOutlined />,
  HistoryOutlined: <HistoryOutlined />,
  FileTextOutlined: <FileTextOutlined />,
  AuditOutlined: <AuditOutlined />,
  UserOutlined: <UserOutlined />,
  CompassOutlined: <CompassOutlined />,
  MessageOutlined: <MessageOutlined />,
};

/** 默认图标 */
export const DEFAULT_ICON = <AppstoreOutlined />;

/** 根据图标字符串名称返回 React 元素，未匹配时返回默认图标 */
export function resolveIcon(iconName?: string): React.ReactNode {
  if (!iconName) return DEFAULT_ICON;
  return ICON_NAME_MAP[iconName] ?? DEFAULT_ICON;
}

/** 用于 Select 的图标选项列表 */
export const ICON_OPTIONS = [
  { value: 'AppstoreOutlined', label: '应用' },
  { value: 'CloudServerOutlined', label: '云服务' },
  { value: 'DatabaseOutlined', label: '数据库' },
  { value: 'LinkOutlined', label: '链接' },
  { value: 'GlobalOutlined', label: '全球' },
  { value: 'SettingOutlined', label: '设置' },
  { value: 'MonitorOutlined', label: '监控' },
  { value: 'ToolOutlined', label: '工具' },
  { value: 'ApiOutlined', label: 'API' },
  { value: 'CodeOutlined', label: '代码' },
  { value: 'BookOutlined', label: '文档' },
  { value: 'BlockOutlined', label: '模块' },
  { value: 'FolderOutlined', label: '目录' },
  { value: 'FileOutlined', label: '文件' },
  { value: 'ThunderboltOutlined', label: '闪电' },
  { value: 'RobotOutlined', label: '机器人' },
  { value: 'TeamOutlined', label: '团队' },
  { value: 'SafetyOutlined', label: '安全' },
];
