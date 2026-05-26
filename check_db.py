import os, sqlite3

db_dir = os.environ.get('DATA_DIR', os.path.join(os.getcwd(), 'data'))
ws_db = os.path.join(db_dir, 'workspace.db')
ingest_db = os.path.join(db_dir, 'ingest', 'ingest.db')

print(f"workspace.db: {ws_db}")
print(f"  exists: {os.path.exists(ws_db)}")

if os.path.exists(ws_db):
    conn = sqlite3.connect(ws_db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"  tables: {tables}")
    if 'workspaces' in tables:
        cur.execute('SELECT id, name, type, status, owner FROM workspaces')
        rows = cur.fetchall()
        print(f"  workspaces: {len(rows)}")
        for r in rows:
            print(f"    id={r[0]}, name={r[1]}, type={r[2]}, status={r[3]}, owner={r[4]}")
    if 'scenarios' in tables:
        cur.execute('SELECT scenario_id, name, workspace_id FROM scenarios')
        rows = cur.fetchall()
        print(f"  scenarios: {len(rows)}")
        for r in rows:
            print(f"    id={r[0]}, name={r[1]}, ws={r[2]}")
    conn.close()

print(f"\ningest.db: {ingest_db}")
print(f"  exists: {os.path.exists(ingest_db)}")

if os.path.exists(ingest_db):
    conn = sqlite3.connect(ingest_db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"  tables: {tables}")
    if 'scenarios' in tables:
        cur.execute('SELECT scenario_id, name FROM scenarios')
        for r in cur.fetchall():
            print(f"    scenario: id={r[0]}, name={r[1]}")
    if 'ontology_documents' in tables:
        cur.execute('SELECT count(*) FROM ontology_documents')
        print(f"    ontology_documents count: {cur.fetchone()[0]}")
    conn.close()

# 检查容器环境数据目录
docker_data = os.path.join(os.getcwd(), 'data')
print(f"\ndata dir: {docker_data}")
print(f"  exists: {os.path.exists(docker_data)}")
if os.path.exists(docker_data):
    for f in os.listdir(docker_data):
        fpath = os.path.join(docker_data, f)
        if os.path.isdir(fpath):
            subfiles = os.listdir(fpath)
            print(f"  {f}/ ({len(subfiles)} files)")
        else:
            print(f"  {f} ({os.path.getsize(fpath)} bytes)")
