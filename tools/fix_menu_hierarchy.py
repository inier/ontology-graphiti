#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('E:/DEMO/AI/ontology-graphiti/data/menu_config.db')
conn.row_factory = sqlite3.Row

# 目录节点：(name, icon, group_paths)
DIRECTORIES = [
    ('系统导航', 'CompassOutlined',    ['/guide']),
    ('本体设计', 'ApartmentOutlined',  ['/ontology/designer','/ontology/graph',
                                         '/business/entities','/business/process',
                                         '/business/rules','/business/indicators',
                                         '/business/logic','/blueprint','/versions']),
    ('智能体',   'RobotOutlined',      ['/agent','/admin/agents','/skills']),
    ('推演仿真', 'ThunderboltOutlined', ['/simulation','/simulator','/simulation/deduction']),
    ('知识库',   'DatabaseOutlined',   ['/knowledge','/knowledge/navigation']),
    ('数据摄入', 'ExperimentOutlined',  ['/ingest']),
    ('工作空间', 'AppstoreOutlined',   ['/workspace/manage']),
    ('系统管理', 'SettingOutlined',    ['/settings','/users','/roles','/audit',
                                         '/i18n-admin','/settings/channels/default',
                                         '/policy-editor','/menu-config']),
]

# 先删除旧的 directory 节点
conn.execute("DELETE FROM menu_items WHERE menu_type='directory'")
# 重置所有子节点 parent_id
conn.execute("UPDATE menu_items SET parent_id = NULL WHERE menu_type='menu'")

now = '2026-07-04T00:00:00'
for idx, (name, icon, paths) in enumerate(DIRECTORIES):
    import uuid
    dir_id = str(uuid.uuid4()).replace('-','')[:12]
    conn.execute('''INSERT INTO menu_items
        (id, parent_id, name, code, menu_type, link_type, path, url,
         icon, sort_order, is_active, is_visible, description, created_at, updated_at)
        VALUES (?, NULL, ?, ?, 'directory', 'internal', '', NULL,
                ?, ?, 1, 1, '', ?, ?)''',
        (dir_id, name, dir_id, icon, idx, now, now))
    for p in paths:
        conn.execute(
            'UPDATE menu_items SET parent_id = ? WHERE path = ? AND parent_id IS NULL',
            (dir_id, p))
    print(f'  {dir_id} [{icon:20s}] {name}: {len(paths)} items')

conn.commit()
print('\nDone. Restart backend or refresh page.')
