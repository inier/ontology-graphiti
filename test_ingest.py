import asyncio
import sys
sys.path.insert(0, '/app')
import os
os.environ.setdefault('DATA_DIR', '/app/data')

from odap.biz.core.ontology.ingestion_split.manual_input import ManualInputHandler
from odap.biz.core.ontology.services.ingest_service import IngestService

svc = IngestService()
print(f"ManualInputHandler.llm is None: {svc.manual_input_handler.llm is None}")
print(f"LLM client type: {type(svc.manual_input_handler.llm)}")

text = '贾宝玉是荣国府的公子，林黛玉是贾母的外孙女。贾宝玉与林黛玉自幼相识，情投意合。薛宝钗是薛姨妈的女儿，后来嫁给了贾宝玉。王熙凤是贾琏之妻，管理荣国府内务。贾母是贾府的最高长辈，疼爱贾宝玉和林黛玉。'

async def test():
    doc = await svc.manual_input_handler.from_natural_language(text, 'test-scenario')
    print(f"Doc entities: {len(doc.entities)}")
    for e in doc.entities:
        print(f"  E: {e.entity_id}: {e.name} ({e.entity_type})")
    print(f"Doc relations: {len(doc.relations)}")
    for r in doc.relations:
        print(f"  R: {r.source_entity} -> {r.target_entity} ({r.relation_type})")

asyncio.run(test())
