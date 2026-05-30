import {
  DatabaseOutlined,
  SwapOutlined,
  ApartmentOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  ExportOutlined,
  RobotOutlined,
  ForkOutlined,
} from '@ant-design/icons';
import type { ReactNode } from 'react';

export type BlueprintNodeType = 'data_source' | 'transform' | 'ontology' | 'action' | 'validation' | 'output' | 'agent' | 'decision';

interface NodeTypeConfig {
  type: BlueprintNodeType;
  label: string;
  color: string;
  icon: ReactNode;
}

export const NODE_TYPE_CONFIG: Record<BlueprintNodeType, NodeTypeConfig> = {
  data_source: { type: 'data_source', label: '数据源', color: '#1890ff', icon: <DatabaseOutlined /> },
  transform: { type: 'transform', label: '转换', color: '#722ed1', icon: <SwapOutlined /> },
  ontology: { type: 'ontology', label: '本体', color: '#13c2c2', icon: <ApartmentOutlined /> },
  action: { type: 'action', label: '动作', color: '#fa8c16', icon: <ThunderboltOutlined /> },
  validation: { type: 'validation', label: '校验', color: '#52c41a', icon: <CheckCircleOutlined /> },
  output: { type: 'output', label: '输出', color: '#eb2f96', icon: <ExportOutlined /> },
  agent: { type: 'agent', label: '智能体', color: '#2f54eb', icon: <RobotOutlined /> },
  decision: { type: 'decision', label: '决策', color: '#faad14', icon: <ForkOutlined /> },
};

export const NODE_TYPE_LIST = Object.values(NODE_TYPE_CONFIG);
