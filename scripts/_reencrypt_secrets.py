"""用（新的、已持久化的）CONFIG_ENCRYPTION_KEY 重新加密 config.db 中的敏感配置项。

背景：旧密钥从未持久化且已丢失，2026-07-19 加密的密文不可恢复。
     本脚本以环境变量中的明文为源，用当前 CONFIG_ENCRYPTION_KEY 重新加密写回。

映射关系取自 config_schema_registry.env_mapping，不硬编码。
"""
import os
import sys

sys.path.insert(0, "/app/apps/api")

REQUIRED = "CONFIG_ENCRYPTION_KEY"
key = os.environ.get(REQUIRED, "")
if not key:
    print(f"[FATAL] 环境变量 {REQUIRED} 未提供，拒绝执行（否则会写入无法解密的密文）")
    sys.exit(2)
print(f"使用密钥: {key[:6]}...{key[-4:]} (len={len(key)})")
print()

from odap.biz.platform.config.impl.config_manager import ConfigManager  # noqa: E402
from odap.infra.security.config_encryption import get_encryption  # noqa: E402

enc = get_encryption()
print(f"加密可用: {enc.available}")
print()

mgr = ConfigManager.get_instance()
schemas = mgr._storage.list_schemas()

print("=" * 80)
print("重新加密敏感项（源：环境变量明文 → 新密钥加密 → 写回 config.db）")
print("=" * 80)
repaired, skipped = [], []
for s in schemas:
    if not s.get("is_sensitive"):
        continue
    ckey = s["key"]
    env_name = s.get("env_mapping")
    if not env_name:
        skipped.append((ckey, "schema 无 env_mapping"))
        continue
    plain = os.environ.get(env_name, "")
    if not plain:
        skipped.append((ckey, f"env {env_name} 为空"))
        continue

    old_stored = mgr.get(ckey)  # 注意：这是解密后的值；解密失败时为密文
    mgr.set(ckey, plain, updated_by="admin")
    masked = plain[:6] + "***" + plain[-4:] if len(plain) > 12 else "***"
    repaired.append((ckey, env_name, masked, len(old_stored or "")))
    print(f"  [OK]  {ckey:26s} <- {env_name:20s} = {masked}")

for ckey, why in skipped:
    print(f"  [SKIP] {ckey:26s} ({why})")

print()
print("=" * 80)
print("回读校验（从存储层读取并尝试解密）")
print("=" * 80)
ok = 0
for s in schemas:
    if not s.get("is_sensitive"):
        continue
    ckey = s["key"]
    items = [i for i in mgr._storage.list_configs() if i["key"] == ckey]
    if not items:
        print(f"  [MISS] {ckey}")
        continue
    it = items[0]
    val = it.get("value") or ""
    env_name = s.get("env_mapping")
    expect = os.environ.get(env_name, "") if env_name else ""
    match = (val == expect)
    ok += 1 if match else 0
    shown = (val[:6] + "***" + val[-4:]) if len(val) > 12 else val
    print(f"  [{'OK' if match else 'MISMATCH'}] {ckey:26s} 解密后 = {shown}")

print()
print(f"校验通过: {ok} 项")
print("next: 带上相同的 CONFIG_ENCRYPTION_KEY 重启 app，日志中不应再出现 Decryption failed")
