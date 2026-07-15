/**
 * 查询输入组件 - 支持模式选择和查询建议
 */
import React, { useState } from 'react';
import { Input, Select, Slider, Space, Tag, Tooltip } from 'antd';
import { SearchOutlined, ThunderboltOutlined, ApiOutlined, BranchesOutlined, ExperimentOutlined } from '@ant-design/icons';
import type { QueryMode } from '../services/nlQueryApi';

const { TextArea } = Input;

const MODE_OPTIONS: { value: QueryMode; label: string; icon: React.ReactNode; color: string }[] = [
  { value: 'auto', label: '自动', icon: <ThunderboltOutlined />, color: '#722ed1' },
  { value: 'keyword', label: '关键词', icon: <SearchOutlined />, color: '#1890ff' },
  { value: 'semantic', label: '语义', icon: <ApiOutlined />, color: '#52c41a' },
  { value: 'graph', label: '图查询', icon: <BranchesOutlined />, color: '#fa8c16' },
];

const SUGGESTIONS = [
  '查找与"孙悟空"相关的所有实体',
  '哪些实体之间存在"师徒"关系？',
  '分析本体中的核心概念和关联',
  '搜索包含"取经"的知识条目',
];

interface QueryInputProps {
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
  onExplain: () => void;
  mode: QueryMode;
  onModeChange: (mode: QueryMode) => void;
  topK: number;
  onTopKChange: (k: number) => void;
  loading: boolean;
}

export function QueryInput({
  value,
  onChange,
  onSearch,
  onExplain,
  mode,
  onModeChange,
  topK,
  onTopKChange,
  loading,
}: QueryInputProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSearch();
    }
  };

  return (
    <div style={{ padding: '16px 20px', borderBottom: '1px solid #f0f0f0', background: '#fafafa' }}>
      <Space orientation="vertical" style={{ width: '100%' }} size={12}>
        {/* 模式选择 + 输入框 */}
        <Space.Compact style={{ width: '100%' }}>
          <Select
            value={mode}
            onChange={onModeChange}
            style={{ width: 120 }}
            options={MODE_OPTIONS.map((o) => ({
              value: o.value,
              label: (
                <Space size={4}>
                  {o.icon}
                  <span>{o.label}</span>
                </Space>
              ),
            }))}
          />
          <TextArea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder='输入自然语言查询，如：查找与"孙悟空"相关的所有实体'
            autoSize={{ minRows: 1, maxRows: 4 }}
            style={{ flex: 1 }}
            disabled={loading}
          />
        </Space.Compact>

        {/* 操作按钮 + 高级设置 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Tooltip title="执行完整查询（五阶段管线）">
              <Tag
                color="blue"
                style={{ cursor: 'pointer', padding: '2px 10px' }}
                onClick={loading ? undefined : onSearch}
              >
                <SearchOutlined /> 查询
              </Tag>
            </Tooltip>
            <Tooltip title="查看查询解释（不执行）">
              <Tag
                color="orange"
                style={{ cursor: 'pointer', padding: '2px 10px' }}
                onClick={loading ? undefined : onExplain}
              >
                <ExperimentOutlined /> 解释
              </Tag>
            </Tooltip>
            <Tag
              color={showAdvanced ? 'geekblue' : 'default'}
              style={{ cursor: 'pointer', padding: '2px 10px' }}
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              高级
            </Tag>
          </Space>

          {/* 当前模式标签 */}
          <Space size={4}>
            {MODE_OPTIONS.filter((o) => o.value === mode).map((o) => (
              <Tag key={o.value} color={o.color} style={{ margin: 0 }}>
                {o.icon} {o.label}模式
              </Tag>
            ))}
          </Space>
        </div>

        {/* 高级设置 */}
        {showAdvanced && (
          <div style={{ padding: '8px 12px', background: '#fff', borderRadius: 6, border: '1px solid #f0f0f0' }}>
            <div style={{ marginBottom: 8 }}>
              <span style={{ fontSize: 12, color: '#666', marginRight: 12 }}>返回结果数 (top_k):</span>
              <Slider
                min={1}
                max={50}
                value={topK}
                onChange={onTopKChange}
                style={{ width: 200, display: 'inline-block', verticalAlign: 'middle' }}
              />
              <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>{topK}</span>
            </div>
          </div>
        )}

        {/* 查询建议 */}
        {value === '' && !loading && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            <span style={{ fontSize: 12, color: '#999', lineHeight: '24px' }}>试试：</span>
            {SUGGESTIONS.map((s, i) => (
              <Tag
                key={i}
                style={{ cursor: 'pointer', fontSize: 12 }}
                onClick={() => onChange(s)}
              >
                {s}
              </Tag>
            ))}
          </div>
        )}
      </Space>
    </div>
  );
}
