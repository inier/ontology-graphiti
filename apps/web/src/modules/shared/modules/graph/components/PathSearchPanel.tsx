import { useState, useCallback } from 'react';
import { Input, Button, Tag, message, Space, Tooltip } from 'antd';
import { SearchOutlined, ClearOutlined, ArrowRightOutlined } from '@ant-design/icons';
import type { GraphNode } from '../types';

interface PathSearchPanelProps {
  nodes: GraphNode[];
  onSearch: (source: string, target: string) => boolean;
  onClear: () => void;
}

export function PathSearchPanel({ nodes, onSearch, onClear }: PathSearchPanelProps) {
  const [source, setSource] = useState('');
  const [target, setTarget] = useState('');
  const [selectedSource, setSelectedSource] = useState<GraphNode | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<GraphNode | null>(null);

  const handleSearch = useCallback(() => {
    if (!selectedSource || !selectedTarget) {
      message.warning('请先选择起止节点');
      return;
    }
    if (selectedSource.id === selectedTarget.id) {
      message.warning('起止节点不能相同');
      return;
    }
    const success = onSearch(selectedSource.id, selectedTarget.id);
    if (!success) {
      message.error('未找到路径，请尝试其他节点');
    } else {
      message.success(`路径搜索成功`);
    }
  }, [selectedSource, selectedTarget, onSearch]);

  const handleClear = useCallback(() => {
    setSource('');
    setTarget('');
    setSelectedSource(null);
    setSelectedTarget(null);
    onClear();
  }, [onClear]);

  const handleNodeSelect = useCallback((node: GraphNode, type: 'source' | 'target') => {
    if (type === 'source') {
      setSelectedSource(node);
      setSource(node.label);
    } else {
      setSelectedTarget(node);
      setTarget(node.label);
    }
  }, []);

  const filteredSourceNodes = nodes.filter(n => 
    n.label.toLowerCase().includes(source.toLowerCase()) && 
    (!selectedTarget || n.id !== selectedTarget.id)
  );

  const filteredTargetNodes = nodes.filter(n => 
    n.label.toLowerCase().includes(target.toLowerCase()) && 
    (!selectedSource || n.id !== selectedSource.id)
  );

  return (
    <div style={{ 
      padding: '12px', 
      background: '#fff', 
      borderRadius: '8px',
      border: '1px solid #f0f0f0',
      boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
    }}>
      <div style={{ fontSize: '14px', fontWeight: '500', marginBottom: '12px', color: '#333' }}>
        最短路径搜索
      </div>
      
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>起点</div>
          <Input
            value={source}
            onChange={(e) => {
              setSource(e.target.value);
              setSelectedSource(null);
            }}
            placeholder="输入节点名称搜索"
            prefix={<SearchOutlined />}
            allowClear
            onKeyDown={(e) => {
              if (e.key === 'Enter' && filteredSourceNodes.length > 0) {
                handleNodeSelect(filteredSourceNodes[0], 'source');
              }
            }}
          />
          {source && filteredSourceNodes.length > 0 && (
            <div style={{ 
              position: 'absolute', 
              top: '52px', 
              left: '0', 
              right: '0', 
              maxHeight: '200px', 
              overflowY: 'auto', 
              background: '#fff', 
              border: '1px solid #e8e8e8',
              borderRadius: '4px',
              zIndex: 100,
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            }}>
              {filteredSourceNodes.map((node) => (
                <div
                  key={node.id}
                  onClick={() => handleNodeSelect(node, 'source')}
                  style={{ 
                    padding: '8px 12px', 
                    cursor: 'pointer',
                    borderBottom: '1px solid #f5f5f5',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#f5f7fa')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '#fff')}
                >
                  <Tag color={node.side === 'red' ? 'red' : node.side === 'blue' ? 'blue' : 'default'}>
                    {node.type}
                  </Tag>
                  <span>{node.label}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <Tooltip title="交换起止节点">
          <Button
            type="text"
            icon={<ArrowRightOutlined />}
            onClick={() => {
              const temp = selectedSource;
              setSelectedSource(selectedTarget);
              setSelectedTarget(temp);
              const tempLabel = source;
              setSource(target);
              setTarget(tempLabel);
            }}
            disabled={!selectedSource || !selectedTarget}
          />
        </Tooltip>

        <div style={{ flex: 1, position: 'relative' }}>
          <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>终点</div>
          <Input
            value={target}
            onChange={(e) => {
              setTarget(e.target.value);
              setSelectedTarget(null);
            }}
            placeholder="输入节点名称搜索"
            prefix={<SearchOutlined />}
            allowClear
            onKeyDown={(e) => {
              if (e.key === 'Enter' && filteredTargetNodes.length > 0) {
                handleNodeSelect(filteredTargetNodes[0], 'target');
              }
            }}
          />
          {target && filteredTargetNodes.length > 0 && (
            <div style={{ 
              position: 'absolute', 
              top: '52px', 
              left: '0', 
              right: '0', 
              maxHeight: '200px', 
              overflowY: 'auto', 
              background: '#fff', 
              border: '1px solid #e8e8e8',
              borderRadius: '4px',
              zIndex: 100,
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            }}>
              {filteredTargetNodes.map((node) => (
                <div
                  key={node.id}
                  onClick={() => handleNodeSelect(node, 'target')}
                  style={{ 
                    padding: '8px 12px', 
                    cursor: 'pointer',
                    borderBottom: '1px solid #f5f5f5',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#f5f7fa')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '#fff')}
                >
                  <Tag color={node.side === 'red' ? 'red' : node.side === 'blue' ? 'blue' : 'default'}>
                    {node.type}
                  </Tag>
                  <span>{node.label}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <Space>
          <Button
            type="primary"
            onClick={handleSearch}
            disabled={!selectedSource || !selectedTarget}
          >
            搜索路径
          </Button>
          <Button
            icon={<ClearOutlined />}
            onClick={handleClear}
          >
            清除
          </Button>
        </Space>
      </div>

      {selectedSource && (
        <div style={{ marginTop: '8px', fontSize: '12px', color: '#666' }}>
          <span>起点: </span>
          <Tag color="green">{selectedSource.label}</Tag>
          <span style={{ marginLeft: '12px' }}>终点: </span>
          <Tag color="orange">{selectedTarget?.label || '未选择'}</Tag>
        </div>
      )}
    </div>
  );
}