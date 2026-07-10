"""
Menu i18n migration: convert name field from Chinese display text to i18n keys,
and code field from UUID to permission codes.

Architecture:
  - name: stores i18n key (e.g. "menu.ontology.designer")
  - code: stores permission code (e.g. "ontology:designer:view")
  - Frontend resolves via t(name, { ns: 'menu-names' })
"""
import sqlite3, os, sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'menu_config.db')

NAME_TO_KEY = {
    '本体设计器': 'menu.ontology.designer',
    '语义图谱': 'menu.ontology.semantic_graph',
    '对象管理': 'menu.ontology.object_management',
    '业务模型': 'menu.ontology.business_model',
    '指标': 'menu.ontology.metrics',
    '逻辑': 'menu.ontology.logic',
    '图谱探索': 'menu.ontology.graph_explore',
    '版本历史': 'menu.ontology.version_history',
    '系统管理': 'menu.system.admin',
    '策略管理': 'menu.system.policy_management',
    '策略编辑器': 'menu.system.policy_management',
    '用户管理': 'menu.system.user_management',
    '角色管理': 'menu.system.role_management',
    '审计日志': 'menu.system.audit_log',
    '国际化': 'menu.system.i18n',
    '系统配置': 'menu.system.config',
    '菜单配置': 'menu.system.menu_config',
    'IM管理': 'menu.system.im_admin',
    'Agent管理': 'menu.agent.management',
    '智能体管理': 'menu.agent.management',
    '本体编辑器': 'menu.agent.ontology_editor',
    'Skill管理': 'menu.agent.skill_management',
    '工作空间': 'menu.workspace.main',
    '知识库': 'menu.knowledge.main',
    '知识图谱': 'menu.knowledge.graph',
    '智能问答': 'menu.qa.main',
    '数据采集': 'menu.data.ingestion',
    '沙盘推演': 'menu.data.sandbox',
    '事件模拟': 'menu.data.event_sim',
    '仿真分析': 'menu.data.simulation',
}

NAME_TO_CODE = {
    'menu.ontology.designer': 'ontology:designer:view',
    'menu.ontology.semantic_graph': 'ontology:graph:view',
    'menu.ontology.object_management': 'ontology:object:manage',
    'menu.ontology.business_model': 'ontology:business:view',
    'menu.ontology.metrics': 'ontology:metrics:view',
    'menu.ontology.logic': 'ontology:logic:view',
    'menu.ontology.graph_explore': 'ontology:explore:view',
    'menu.ontology.version_history': 'ontology:version:view',
    'menu.system.admin': 'system:admin',
    'menu.system.policy_management': 'system:policy:manage',
    'menu.system.user_management': 'system:user:manage',
    'menu.system.role_management': 'system:role:manage',
    'menu.system.audit_log': 'system:audit:view',
    'menu.system.i18n': 'system:i18n:manage',
    'menu.system.config': 'system:config:manage',
    'menu.system.menu_config': 'system:menu:config',
    'menu.system.im_admin': 'system:im:admin',
    'menu.agent.management': 'agent:agents:manage',
    'menu.agent.ontology_editor': 'agent:ontology:edit',
    'menu.agent.skill_management': 'agent:skill:manage',
    'menu.workspace.main': 'workspace:view',
    'menu.knowledge.main': 'knowledge:base:view',
    'menu.knowledge.graph': 'knowledge:graph:view',
    'menu.qa.main': 'qa:view',
    'menu.data.ingestion': 'data:ingest:view',
    'menu.data.sandbox': 'data:sandbox:view',
    'menu.data.event_sim': 'data:event:sim',
    'menu.data.simulation': 'data:simulation:view',
}


def migrate():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('SELECT id, name, code FROM menu_items').fetchall()

    updated_name = 0
    updated_code = 0

    for row in rows:
        db_id, db_name, db_code = row
        key = NAME_TO_KEY.get(db_name)
        perm_code = NAME_TO_CODE.get(key) if key else None

        if key and key != db_name:
            conn.execute('UPDATE menu_items SET name=? WHERE id=?', (key, db_id))
            updated_name += 1
            print(f'  name: "{db_name}" → "{key}"')

        code_is_uuid = (db_code == db_id or (len(db_code) >= 32 and len(set(db_code)) > 5))
        if perm_code and code_is_uuid:
            conn.execute('UPDATE menu_items SET code=? WHERE id=?', (perm_code, db_id))
            updated_code += 1
            print(f'  code: "{db_code[:12]}..." → "{perm_code}"')

    conn.commit()
    conn.close()
    print(f'\nMigration complete: {updated_name} names updated, {updated_code} codes updated')


if __name__ == '__main__':
    if '--dry-run' in sys.argv:
        print('[DRY RUN] Would update name→i18n keys and code→permission codes')
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute('SELECT name, code FROM menu_items').fetchall()
        for r in rows:
            key = NAME_TO_KEY.get(r[0])
            print(f'  {r[0]:16s} → {key or "NO_KEY":35s} | code={r[1][:15]}')
        conn.close()
    else:
        print(f'Migrating {DB_PATH}...')
        migrate()
