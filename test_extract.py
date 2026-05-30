from odap.biz.core.ontology.ingestion_split.manual_input import ManualInputHandler
import asyncio

handler = ManualInputHandler()
text = "贾宝玉是荣国府的公子，林黛玉是贾母的外孙女。贾宝玉与林黛玉在荣国府相识相知，两人情投意合。薛宝钗是薛姨妈的女儿，后来也住进了荣国府。王熙凤是贾琏的妻子，掌管荣国府的家务。贾母是荣国府的老祖宗，非常疼爱贾宝玉和林黛玉。"

result = asyncio.run(handler.from_natural_language(text, 'test-scenario'))

print("=== Entities ===")
for e in result.entities:
    print(f"  {e.name} ({e.entity_type})")

print(f"\n=== Relations ({len(result.relations)}) ===")
for r in result.relations:
    src_name = next((e.name for e in result.entities if e.entity_id == r.source_entity), r.source_entity)
    tgt_name = next((e.name for e in result.entities if e.entity_id == r.target_entity), r.target_entity)
    print(f"  {r.relation_type}: {src_name} -> {tgt_name}")

print(f"\nTotal: {len(result.entities)} entities, {len(result.relations)} relations")
