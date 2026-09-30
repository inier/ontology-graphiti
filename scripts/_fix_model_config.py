"""把 llm.model 写入配置库（保留修订审计），并打印前后值。

背景：DB 中的 llm.model 是测试残值 gpt-4o-imported（2026-09-10 由 test-user 写入），
     优先级高于 ENV，必须一并修正。
"""
import sqlite3
import sys

sys.path.insert(0, "/app/apps/api")

DB = "/app/data/config.db"
NEW_MODEL = "openai/gpt-oss-20b"


def dump(tag):
    c = sqlite3.connect(DB)
    rows = c.execute(
        "SELECT key, value, updated_at, updated_by FROM config_items "
        "WHERE key IN ('llm.model','llm.api_base') ORDER BY key"
    ).fetchall()
    print(f"  [{tag}]")
    for k, v, ts, by in rows:
        if "key" in k:
            v = (v[:6] + "***" + v[-4:]) if v and len(v) > 12 else v
        print(f"    {k:14s} = {v!r}   (updated_at={ts}, by={by})")


print("=" * 70)
print("修正前")
print("=" * 70)
dump("before")

from odap.biz.platform.config.impl.config_manager import ConfigManager  # noqa: E402

mgr = ConfigManager.get_instance()
print()
print(f"当前 ConfigManager 视角 llm.model = {mgr.get('llm.model')!r}")

old = mgr.set("llm.model", NEW_MODEL, updated_by="admin")
print(f"已写入: {old!r} -> {NEW_MODEL!r}")

print()
print("=" * 70)
print("修正后")
print("=" * 70)
dump("after")

print()
print("=" * 70)
print("修订记录(config_revisions 最近 3 条)")
print("=" * 70)
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
cols = [r[1] for r in c.execute("PRAGMA table_info(config_revisions)").fetchall()]
print("  列:", cols)
for r in c.execute(
    "SELECT * FROM config_revisions ORDER BY revision_number DESC LIMIT 3"
).fetchall():
    d = dict(r)
    print("  " + str({k: (str(v)[:70] if v is not None else None) for k, v in d.items()}))
