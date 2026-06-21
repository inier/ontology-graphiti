import { useState } from 'react';
import { List, Button, Tag, Modal, Input, Space, message } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { PlusOutlined, DeleteOutlined, ForkOutlined } from '@ant-design/icons';
import { useBlueprintStore } from '@/modules/ontology/stores/blueprintStore';
import { blueprintApi } from '@/modules/ontology/services/blueprintApi';

export function BlueprintList() {
  const { blueprints, currentBlueprint, loadBlueprint, createBlueprint, deleteBlueprint } = useBlueprintStore();
  const [createVisible, setCreateVisible] = useState(false);
  const [newName, setNewName] = useState('');
  const [forkVisible, setForkVisible] = useState(false);
  const [forkName, setForkName] = useState('');
  const [forkId, setForkId] = useState('');

  const handleCreate = async () => {
    if (!newName.trim()) {
      message.warning('请输入蓝图名称');
      return;
    }
    try {
      await createBlueprint(newName.trim());
      setNewName('');
      setCreateVisible(false);
      message.success('蓝图已创建');
    } catch {
      message.error('创建蓝图失败');
    }
  };

  const handleDelete = (blueprintId: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除此蓝图吗？此操作不可恢复。',
      okType: 'danger',
      onOk: async () => {
        await deleteBlueprint(blueprintId);
        message.success('蓝图已删除');
      },
    });
  };

  const handleFork = async () => {
    if (!forkName.trim()) {
      message.warning('请输入蓝图名称');
      return;
    }
    try {
      const forked = await blueprintApi.fork(forkId, forkName.trim());
      await loadBlueprint(forked.blueprint_id);
      setForkName('');
      setForkVisible(false);
      message.success('蓝图已分叉');
    } catch {
      message.error('分叉蓝图失败');
    }
  };

  const openFork = (blueprintId: string) => {
    setForkId(blueprintId);
    setForkName('');
    setForkVisible(true);
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#666' }}>蓝图列表</span>
        <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => setCreateVisible(true)}>
          新建
        </Button>
      </div>

      <List
        size="small"
        dataSource={blueprints}
        renderItem={item => (
          <List.Item
            style={{
              padding: '4px 0',
              cursor: 'pointer',
              background: currentBlueprint?.blueprint_id === item.blueprint_id ? '#e6f7ff' : 'transparent',
              borderRadius: 4,
            }}
            onClick={() => loadBlueprint(item.blueprint_id)}
          >
            <Card
              size="small"
              style={{ width: '100%', border: currentBlueprint?.blueprint_id === item.blueprint_id ? '1px solid #1890ff' : undefined }}
              styles={{ body: { padding: '8px 12px' } }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 500, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {item.name}
                  </div>
                  <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>
                    v{item.version} · {item.updated_at?.slice(0, 10) || '-'}
                  </div>
                </div>
                <Space size={4}>
                  <Tag color={item.is_published ? 'green' : 'default'} style={{ fontSize: 11, margin: 0 }}>
                    {item.is_published ? '已发布' : '草稿'}
                  </Tag>
                  <Button size="small" type="text" icon={<ForkOutlined />} onClick={e => { e.stopPropagation(); openFork(item.blueprint_id); }} />
                  <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={e => { e.stopPropagation(); handleDelete(item.blueprint_id); }} />
                </Space>
              </div>
            </Card>
          </List.Item>
        )}
        locale={{ emptyText: '暂无蓝图' }}
      />

      <Modal title="新建蓝图" open={createVisible} onOk={handleCreate} onCancel={() => setCreateVisible(false)} okText="创建" cancelText="取消">
        <Input placeholder="请输入蓝图名称" value={newName} onChange={e => setNewName(e.target.value)} onPressEnter={handleCreate} />
      </Modal>

      <Modal title="分叉蓝图" open={forkVisible} onOk={handleFork} onCancel={() => setForkVisible(false)} okText="分叉" cancelText="取消">
        <Input placeholder="请输入新蓝图名称" value={forkName} onChange={e => setForkName(e.target.value)} onPressEnter={handleFork} />
      </Modal>
    </div>
  );
}
