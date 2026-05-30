import sqlite3, json, os
db_path = '/app/data/ingest/ingest.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(ontology_documents)')
cols = cursor.fetchall()
for c in cols:
    print(f"  col: {c[1]} ({c[2]})")
cursor.execute('SELECT doc_id, entities, relations FROM ontology_documents ORDER BY rowid DESC LIMIT 1')
row = cursor.fetchone()
if row:
    entities = json.loads(row[1]) if row[1] else []
    relations = json.loads(row[2]) if row[2] else []
    print(f"Latest doc: entities={len(entities)}, relations={len(relations)}")
    for e in entities[:5]:
        print(f"  E: {e.get('entity_id')}: {e.get('name')} ({e.get('entity_type')})")
    for r in relations[:5]:
        print(f"  R: {r.get('source_entity')} -> {r.get('target_entity')} ({r.get('relation_type')})")
cursor.execute('SELECT scenario_id, doc_id FROM scenario_documents')
for row in cursor.fetchall():
    print(f"scenario_doc: scenario_id={row[0]}, doc_id={row[1]}")
conn.close()
