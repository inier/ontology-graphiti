# Tasks: æ¬ä½è®¾è®¡å¨å½»åºéæ?â?US3 èªç¶è¯­è¨æåå¢å¼º

**Input**: Design documents from `/specs/003-ontology-redesign/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Scope**: æ¬ä»»å¡æ¸åèç?US3ï¼èªç¶è¯­è¨æåå¢å¼º + Hyper-Extract éæï¼ï¼æ¶µç FR-021 ~ FR-031ã? ä¸ªéªæ¶åºæ¯ã?2 ä¸?Edge CasesãUS1/US2/US4/US5 çä»»å¡è§å?tasks.mdã?
## Format: `[ID] [P?] [TDD?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[TDD]**: Must follow RED-GREEN-REFACTOR discipline
- **[REVIEW]**: Requires code review before proceeding
- **[SUBAGENT]**: Can be delegated to a subagent

---

## Phase 1: Setup (HE ä¾èµéæ)

**Purpose**: å°?Hyper-Extract éæå?ODAP é¡¹ç®ä¸­ï¼å®è£ä¾èµï¼åå»ºæ¨¡åéª¨æ?
- [x] T001 å?`requirements.txt` ä¸­æ·»å?Hyper-Extract ä¾èµï¼`-e ./hyper-extract`ã`langchain`ã`langchain-openai`ã`faiss-cpu`ã`ontomem`ã`ontosight`ã`semhash`ï¼æ·»å ææ¡£è§£æä¾èµï¼`PyPDF2`ã`python-docx`ã`openpyxl`ã`pytesseract`ã`Pillow`
- [x] T002 [P] å?`docker/Dockerfile` ä¸­æ·»å ç³»ç»ä¾èµï¼`tesseract-ocr`ã`tesseract-ocr-chi-sim`ï¼ä¸­æ?OCR è¯­è¨åï¼ï¼ç¡®ä¿?Docker éåæå»ºåå« HE è¿è¡ç¯å¢
- [x] T003 [P] åå»º `odap/biz/core/ontology/extraction/` æ¨¡åéª¨æ¶ï¼æ AGENTS.md biz æ¨¡å 6 å±ç»æï¼ï¼?  ```
  extraction/
  âââ api/routes.py
  âââ api/schemas.py
  âââ models/extraction_models.py
  âââ interfaces/extraction_interfaces.py
  âââ impl/he_adapter.py
  âââ impl/ontology_mapper.py
  âââ impl/document_parser.py
  âââ impl/template_generator.py
  âââ impl/provenance_tracker.py
  âââ services/extraction_service.py
  âââ storage/sqlite_extraction_storage.py
  ```
- [x] T004 [P] åå»ºåç«¯æ¨¡åéª¨æ¶ï¼?  ```
  frontend/src/modules/ontology/components/
  âââ NLExtractor.tsx          (éæç°æ)
  âââ DocumentUploader.tsx     (æ°å¢)
  âââ KnowledgeBaseSelector.tsx (æ°å¢)
  âââ ExtractionPreview.tsx    (éæç°æ)
  âââ ProvenanceViewer.tsx     (æ°å¢)
  âââ TemplateRecommender.tsx  (æ°å¢)
  ```

**Checkpoint**: HE ä¾èµå¯å¯¼å¥ï¼æ¨¡åéª¨æ¶åå»ºå®æï¼Docker éåå¯æå»?
---

## Phase 2: Foundational (æ ¸å¿ééå±?

**Purpose**: å®ç° Hyper-Extract Python API ééãæ¬ä½æ å°å¨ãææ¡£è§£æå¨ââææä¸å±åè½çåç½®ä¾èµ

**â ï¸ CRITICAL**: Phase 3+ çææä»»å¡é½ä¾èµæ¬é¶æ®µå®æ?
- [x] T005 [TDD] å®ç° `odap/biz/core/ontology/extraction/impl/he_adapter.py` â?HE Python API ééå¨ï¼
  - `HEAdapter` ç±»ï¼å°è£ `Template.create()`ã`AutoType.parse()`ã`feed_text()`ã`merge_batch_data()`ã`build_index()`ã`search()`
  - `extract_from_text(text, template_config)` â?è¿å `KnowledgeAbstract` ç»æåæ°æ?  - `extract_incremental(ka_path, text)` â?å¢éæå
  - `merge_results(data_list)` â?æ¹éåå¹¶
  - éçº§æ¨¡å¼ï¼HE å¯¼å¥å¤±è´¥æ¶åéå?`SchemaLevelExtractor`
  - æµè¯ï¼`tests/unit/test_he_adapter.py`ï¼mock HE ä¾èµï¼?
- [x] T006 [TDD] [P] å®ç° `odap/biz/core/ontology/extraction/impl/ontology_mapper.py` â?HE æåç»æå?ODAP æ¬ä½æ¨¡åçæ å°å¨ï¼?  - `OntologyMapper` ç±»ï¼å°?HE `KnowledgeAbstract`ï¼èç?è¾¹ï¼æ å°ä¸?ODAP ç?Schema å±å®ä¹?+ Instance å±æ°æ?  - `map_to_schema(ka_result)` â?7 ç±»ç±»åå®ä¹ï¼ObjectType/LinkType/ActionType/RuleType/ProcessType/FunctionType/IndicatorTypeï¼?  - `map_to_instances(ka_result)` â?å®ä½å®ä¾ + å³ç³»å®ä¾
  - å±æ§æ å°ï¼HE èç¹å±æ?â?ODAP ObjectType.propertiesï¼HE è¾¹å±æ?â?ODAP LinkType.cardinality
  - æµè¯ï¼`tests/unit/test_ontology_mapper.py`

- [x] T007 [TDD] [P] å®ç° `odap/biz/core/ontology/extraction/impl/document_parser.py` â?ææ¡£è§£æç®¡çº¿ï¼?  - `DocumentParser` ç±»ï¼ç»ä¸ææ¡£è§£æå¥å£
  - `parse_pdf(file_path)` â?ææ¬ï¼ä½¿ç?PyPDF2ï¼?  - `parse_docx(file_path)` â?ææ¬ï¼ä½¿ç?python-docxï¼?  - `parse_txt(file_path)` â?ææ¬
  - `parse_csv(file_path)` â?ç»æåææ¬æè¿?  - `parse_excel(file_path)` â?ç»æåææ¬æè¿°ï¼ä½¿ç¨ openpyxlï¼?  - `parse_image(file_path)` â?OCR ææ¬ï¼ä½¿ç?pytesseractï¼?  - `parse_json(file_path)` â?ç»æåææ¬æè¿?  - `parse_xml(file_path)` â?ç»æåææ¬æè¿?  - `parse(file_path)` â?èªå¨æ£æµæ ¼å¼å¹¶è·¯ç±
  - `chunk_text(text, max_tokens=4000)` â?ææ¬åå
  - æµè¯ï¼`tests/unit/test_document_parser.py`ï¼ä½¿ç?tmp_path fixtureï¼?
- [x] T008 [TDD] [P] å®ç° `odap/biz/core/ontology/extraction/impl/template_generator.py` â?HE æ¨¡æ¿çæå¨ï¼
  - `TemplateGenerator` ç±»ï¼
  - `generate_from_ontology(ontology_id)` â?ä»æ¬ä½å®ä¹èªå¨çæ?HE YAML æ¨¡æ¿
  - `select_preset(domain_hint)` â?ä»?HE 80+ é¢è®¾æ¨¡æ¿ä¸­éæ©å¹éæ¨¡æ¿
  - `generate_with_web_search(text)` â?èç½æç´¢è¾å©å¨æçææ¨¡æ?  - `recommend_templates(text, top_k=3)` â?æ¨èæå¹éçæ¨¡æ?  - ä¸çº§åéç­ç¥ï¼æ¬ä½å®ä¹èªå¨çæ?â?é¢è®¾æ¨¡æ¿ â?èç½æç´¢å¨æçæ?  - æµè¯ï¼`tests/unit/test_template_generator.py`

- [x] T009 [TDD] [P] å®ç° `odap/biz/core/ontology/extraction/impl/provenance_tracker.py` â?å¨é¾è·¯æº¯æºè¿½è¸ªå¨ï¼?  - `ProvenanceTracker` ç±»ï¼
  - `record_extraction(entity_id, source_doc_id, chunk_id, fragment_id, method, template_version)` â?è®°å½æº¯æºä¿¡æ¯
  - `get_provenance(entity_id)` â?æ¥è¯¢æº¯æºé?  - `get_entities_by_source(source_doc_id)` â?ååæ¥è¯¢ï¼æææ¡£äº§çäºåªäºå®ä½?  - æº¯æºæ°æ®ç»æï¼`ExtractionProvenance`ï¼source_doc_id, vector_chunk_id, doc_fragment_id, timestamp, extraction_method, he_template_versionï¼?  - æµè¯ï¼`tests/unit/test_provenance_tracker.py`

**Checkpoint**: 5 ä¸ªæ ¸å¿ééå¨å¨é¨å®ç°å¹¶éè¿æµè¯ï¼HE æåè½åå¯ç¨

---

## Phase 3: US3-AS1/AS5 â?NL ææ¬æå + æ¨¡æ¿åé (æ ¸å¿è·¯å¾)

**Goal**: ç¨æ·è¾å¥ NL ææ¬ï¼ç³»ç»ä½¿ç?HE æ¨¡æ¿åæåï¼æ¯ææ¨¡æ¿ä¸çº§åé

**Independent Test**: è¾å¥"çµåç³»ç»éè¦ç®¡çç¨æ·ãåååè®¢å"ï¼éªè¯æåçå¯¹è±¡ç±»åãå³ç³»ç±»å?
### Tests

- [x] T010 [TDD] [US3] `tests/unit/test_extraction_service.py` â?ExtractionService æ ¸å¿é»è¾æµè¯ï¼?  - `test_extract_from_nl_success` â?æ­£å¸¸æåæµç¨
  - `test_extract_from_nl_empty_text` â?ç©ºææ¬æç»ï¼EC-001ï¼?  - `test_extract_from_nl_template_fallback` â?æ¨¡æ¿ä¸çº§åé
  - `test_extract_from_nl_he_unavailable` â?HE ä¸å¯ç¨æ¶éçº§ï¼EC-008ï¼?  - `test_extract_from_nl_llm_timeout` â?LLM è¶æ¶å¤çï¼EC-007ï¼?
### Implementation

- [x] T011 [US3] éæ `odap/biz/core/ontology/extraction/services/extraction_service.py` â?ç?HE æ¿ä»£ SchemaLevelExtractorï¼?  - `extract_from_nl(ontology_id, text, auto_search=False)` â?åå»ºä¼è¯ â?è°ç¨ HEAdapter â?OntologyMapper æ å° â?å²çªæ£æµ?â?æ´æ°ä¼è¯
  - ä¿ç `extract_from_database()` ä¸å
  - ä¿ç `confirm_extraction()` ä¸å
  - æ°å¢éçº§é»è¾ï¼HE å¯¼å¥å¤±è´¥æ¶åéå?SchemaLevelExtractor
  - æ°å¢æ¨¡æ¿ä¸çº§åéï¼TemplateGenerator.generate_from_ontology â?select_preset â?generate_with_web_search

- [x] T012 [US3] æ´æ° `odap/biz/core/ontology/extraction/api/schemas.py` â?æ©å±è¯·æ±/ååºæ¨¡åï¼?  - `NLExtractionRequest` æ°å¢ `source_type: str = "text"`ã`template_id: Optional[str]`ã`method: Optional[str]`ï¼HE æåæ¹æ³ï¼å¦ graph_rag/light_ragï¼?  - `ExtractionSessionResponse` æ°å¢ `template_used: Optional[str]`ã`provenance_summary: Optional[Dict]`

- [x] T013 [US3] æ´æ° `odap/biz/core/ontology/extraction/api/routes.py` â?è·¯ç±å¢å¼ºï¼?  - `POST /api/extraction/extract/natural-language` æ¯æ `source_type`ã`template_id`ã`method` åæ°
  - `GET /api/extraction/templates` â?æ°å¢ï¼ååºå¯ç?HE æ¨¡æ¿
  - `POST /api/extraction/templates/recommend` â?æ°å¢ï¼æ ¹æ®ææ¬æ¨èæ¨¡æ?
- [x] T014 [US3] éæåç«¯ `NLExtractor.tsx`ï¼?  - 3 ä¸?Tabï¼ææ¬è¾å?/ ææ¡£ä¸ä¼  / ç¥è¯åºéæ©
  - ææ¬è¾å¥ Tabï¼ä¿çç°æ?TextArea + auto_search å¼å³ï¼æ°å¢æ¨¡æ¿éæ©ä¸æåæ¹æ³éæ©
  - è°ç¨ `ontologyApi.extraction.extractNL()` ä¼ å¥ `source_type: "text"`

**Checkpoint**: NL ææ¬æåèµ?HE å¼æï¼æ¨¡æ¿åéå¯ç¨ï¼åç«?3-Tab å¸å±å°±ç»ª

---

## Phase 4: US3-AS2 â?ææ¡£ä¸ä¼ æå

**Goal**: ç¨æ·ä¸ä¼ ææ¡£ï¼PDF/Word/TXT/CSV/Excel/JSON/XML/å¾çï¼ï¼ç³»ç»è§£æåæå?
**Independent Test**: ä¸ä¼ ä¸ä¸?PDF æä»¶ï¼éªè¯è§£æåæåæµç¨

### Implementation

- [x] T015 [TDD] [US3] åç«¯ææ¡£ä¸ä¼  API â?`odap/biz/core/ontology/extraction/api/routes.py` æ°å¢ç«¯ç¹ï¼?  - `POST /api/extraction/extract/document` â?æ¥æ¶æä»¶ä¸ä¼ ï¼multipart/form-dataï¼?  - è¯·æ±æ¨¡åï¼`DocumentExtractionRequest`ï¼ontology_id, file, template_id, methodï¼?  - æµç¨ï¼ä¿å­æä»?â?DocumentParser.parse() â?åå â?HEAdapter.extract_from_text() æ¯å â?merge_results() â?OntologyMapper â?å²çªæ£æµ?  - å¤§æä»¶éå¶ï¼100MBï¼EC-002ï¼?  - æ ¼å¼æ ¡éªï¼ä»åè®¸æå®æ ¼å¼ï¼EC-003ï¼?  - æµè¯ï¼`tests/unit/test_extraction_routes.py`

- [x] T016 [US3] å®ç° `odap/biz/core/ontology/extraction/services/extraction_service.py` æ°å¢æ¹æ³ï¼?  - `extract_from_document(ontology_id, file_path, template_id=None, method=None)` â?ææ¡£è§£æ â?ååæå â?åå¹¶
  - ååå¤±è´¥å¤çï¼è·³è¿å¤±è´¥åï¼æ è®°ä¾éè¯ï¼EC-006ï¼?  - æº¯æºè®°å½ï¼æ¯ä¸ªååçæåç»æé½è®°å½?ProvenanceTracker

- [x] T017 [US3] åç«¯ `DocumentUploader.tsx` ç»ä»¶ï¼?  - Ant Design `Upload.Dragger` ææ½ä¸ä¼ 
  - æ¯ææ ¼å¼æç¤ºï¼PDF/Word/TXT/Markdown/CSV/Excel/JSON/XML/å¾ç
  - æä»¶å¤§å°æ ¡éªï¼?00MB éå¶ï¼?  - ä¸ä¼ è¿åº¦æ?  - ä¸ä¼ æååèªå¨è§¦åæå?
- [x] T018 [US3] åç«¯ `NLExtractor.tsx` ææ¡£ä¸ä¼  Tab éæï¼?  - åµå¥ `DocumentUploader` ç»ä»¶
  - æåä¸­æ¾ç¤ºååè¿åº¦ï¼å·²å¤ç?X/Y åï¼
  - è°ç¨ `ontologyApi.extraction.extractDocument()`

**Checkpoint**: ææ¡£ä¸ä¼ æåå¨æµç¨å¯ç¨ï¼å¤§ææ¡£åååå¹¶æ­£å¸?
---

## Phase 5: US3-AS3 â?ç¥è¯åºéæ©æå

**Goal**: ç¨æ·éæ©ç¥è¯åºï¼ç³»ç»éç¯å¢éæåå¹¶åå¹?
**Independent Test**: éæ©ä¸ä¸ªå·²æç¥è¯åºï¼éªè¯éç¯æåååå¹¶æµç¨?
### Implementation

- [x] T019 [TDD] [US3] åç«¯ç¥è¯åºæå?API â?`odap/biz/core/ontology/extraction/api/routes.py` æ°å¢ç«¯ç¹ï¼?  - `POST /api/extraction/extract/knowledge-base` â?æ¥æ¶ kb_id
  - è¯·æ±æ¨¡åï¼`KBExtractionRequest`ï¼ontology_id, kb_id, template_id, method, batch_size=10ï¼?  - æµç¨ï¼è¯»åç¥è¯åºææ¡£åè¡¨ â?éç¯ DocumentParser.parse() â?HEAdapter.extract_incremental() â?åå¹¶
  - ç©ºç¥è¯åºå¤çï¼EC-004ï¼?  - æéæ ¡éªï¼ç¨æ·ææè®¿é®è¯¥ç¥è¯åºï¼EC-017ï¼?  - æµè¯ï¼`tests/unit/test_extraction_service_kb.py`

- [x] T020 [US3] å®ç° `extraction_service.py` æ°å¢æ¹æ³ï¼?  - `extract_from_knowledge_base(ontology_id, kb_id, template_id=None, method=None, batch_size=10)` â?è¯»å KB ææ¡£ â?éç¯å¢éæå â?åå¹¶
  - ä½¿ç¨ HE `feed_text()` å¢éæåï¼æ¯ç¯æåååå¹¶å°å½åç»æ?  - åæ¹å¤çï¼æ¯æ?batch_size ç¯ï¼é¿ååå­æº¢åºï¼EC-013ï¼?  - ç©ºææ¡£è·³è¿ï¼EC-010ï¼?  - æº¯æºè®°å½ï¼æ¯ç¯ææ¡£çæåç»æé½è®°å½?ProvenanceTracker

- [x] T021 [US3] åç«¯ `KnowledgeBaseSelector.tsx` ç»ä»¶ï¼?  - ç¥è¯åºåè¡¨ï¼è°ç¨ `/api/knowledge-bases`ï¼?  - ææ¡£é¢è§ï¼éä¸­ç¥è¯åºåå±ç¤ºææ¡£åè¡¨åæ°é?  - æ¹ééæ©ï¼å¯éæ©å¨é¨æé¨åææ¡?  - æåè¿åº¦ï¼å·²å¤ç X/Y ç¯ææ¡?
- [x] T022 [US3] åç«¯ `NLExtractor.tsx` ç¥è¯åºéæ© Tab éæï¼?  - åµå¥ `KnowledgeBaseSelector` ç»ä»¶
  - è°ç¨ `ontologyApi.extraction.extractKB()`
  - æåä¸­æ¾ç¤ºéç¯è¿åº¦

**Checkpoint**: ç¥è¯åºå¢éæåå¨æµç¨å¯ç¨ï¼æº¯æºä¿¡æ¯å®æ?
---

## Phase 6: US3-AS4/AS6/AS8 â?é¢è§å¢å¼º + æº¯æºå±ç¤º + å²çªå¤ç

**Goal**: æåç»æé¢è§æ¯æ Schema + Instance åå±å±ç¤ºãå¨é¾è·¯æº¯æºæ¥çãå²çªå¤ç?
**Independent Test**: æåå®æåæ¥ç?Schema å±å®ä¹å Instance å±æ°æ®ï¼ç¹å»å®ä½æ¥çæº¯æºä¿¡æ¯

### Implementation

- [x] T023 [US3] éæ `ExtractionPreview.tsx` â?åå±å±ç¤ºï¼?  - ä¸¤ä¸ªä¸?Tabï¼Schema å±ï¼7 ç±»ç±»åå®ä¹ï¼+ Instance å±ï¼å®ä½/å³ç³»å®ä¾ï¼?  - Schema å±?Tabï¼å¤ç¨ç°æ?7 ç±»ç±»å?AdvancedTable
  - Instance å±?Tabï¼å®ä½åè¡?+ å³ç³»åè¡¨ï¼æ¯è¡å¯å¾éå¯¼å?  - ç»è®¡æ¦è§ï¼Schema å±?X ä¸ªç±»åå®ä¹?+ Instance å±?Y ä¸ªå®ä½?+ Z ä¸ªå³ç³?
- [x] T024 [US3] å®ç° `ProvenanceViewer.tsx` â?æº¯æºä¿¡æ¯æ¥çç»ä»¶ï¼?  - å®ä½/å³ç³»è¡ä¸ç?æº¯æº"å¾æ æé®
  - ç¹å»å¼¹åº Drawer/Modalï¼å±ç¤ºï¼
    - æ¥æºææ¡£åç§° + ID
    - åéåç ID
    - ææ¡£ç¢ç ID
    - æåæ¶é´æ?    - æåæ¹æ³ï¼å¦ graph_ragï¼?    - HE æ¨¡æ¿çæ¬
  - "æ¥çåæ"æé®ï¼è·³è½¬å°ç¥è¯åºææ¡£è¯¦æé¡µ

- [x] T025 [US3] åç«¯æº¯æºæ¥è¯¢ API â?`routes.py` æ°å¢ç«¯ç¹ï¼?  - `GET /api/extraction/provenance/{entity_id}` â?æ¥è¯¢å®ä½æº¯æºä¿¡æ¯
  - `GET /api/extraction/provenance/by-source/{doc_id}` â?ååæ¥è¯¢ï¼æææ¡£äº§çäºåªäºå®ä½?
- [x] T026 [US3] å®ç°æº¯æºå­å¨ â?`sqlite_extraction_storage.py` æ°å¢ï¼?  - `extraction_provenance` è¡¨ï¼entity_id, source_doc_id, vector_chunk_id, doc_fragment_id, timestamp, extraction_method, he_template_version
  - `save_provenance()`ã`get_provenance()`ã`get_provenance_by_source()`

- [x] T027 [US3] å²çªæ£æµå¢å¼?â?`extraction_service.py` æ©å± `_detect_conflicts()` å?`_find_existing_type()`ï¼?  - ä¿®å¤ F4ï¼`_find_existing_type()` æ©å±å°ææ?7 ç±»ç±»åï¼ä¸ä»æ?object_typesï¼?  - ä¿®å¤ F1ï¼`confirm_extraction()` ä¸?`json.loads()` å?try/except é²å¾¡
  - å²çªç±»åï¼duplicate_name + similar_nameï¼Levenshteinï¼? schema_mismatchï¼å±æ§ç»æä¸ä¸è´ï¼

**Checkpoint**: é¢è§æ¯æåå±å±ç¤ºï¼æº¯æºå¯æ¥çï¼å²çªæ£æµè¦çææç±»å?
---

## Phase 7: US3-AS7 â?åééåå¥

**Goal**: ç¡®è®¤å¯¼å¥æ¶éè¿åééäºè¡¥åå¥ Neo4j

**Independent Test**: ç¡®è®¤å¯¼å¥åï¼éªè¯ Neo4j ä¸­æ¢æå®æ´å±æ§ï¼éé Aï¼åæåæ¶æç´¢å¼ï¼éé Bï¼?
### Implementation

- [x] T028 [TDD] [US3] å®ç° `extraction_service.py` åééåå¥é»è¾ï¼?  - `confirm_extraction()` éæï¼?    - éé Aï¼`GraphWriteProxy.write_entity()` åå¥å®æ´å±æ§å° Neo4jï¼å« Provenance å±æ§ï¼
    - éé Bï¼`graphiti.add_episode()` åå¥ç»æåæè¦ï¼OntologyDocument JSONï¼?  - éé B å¤±è´¥å¤çï¼æ è®°å¤±è´¥ï¼åå°å¼æ­¥éè¯ï¼EC-011ï¼?  - äºå¡æ§ï¼éé A æååéé B å¤±è´¥ä¸åæ»ï¼è®°å½å¤±è´¥ç¶æ?  - æµè¯ï¼`tests/unit/test_extraction_service_confirm.py`

- [x] T029 [US3] åç«¯ç¡®è®¤å¯¼å¥æµç¨å¢å¼ºï¼?  - ç¡®è®¤å¼¹çªæ¾ç¤ºåå¥è¿åº¦ï¼éé A â?â?éé B â?  - éé B å¤±è´¥æ¶æç¤?ç´¢å¼åå¥å¤±è´¥ï¼æ°æ®å·²ä¿å­ä½æç´¢åè½å¯è½å»¶è¿?
  - å¯¼å¥æååèªå¨å·æ°æ¬ä½æ°æ?
**Checkpoint**: åééåå¥å¯ç¨ï¼éé B å¤±è´¥æéçº§å¤ç?
---

## Phase 8: US3-AS9 â?å¤æ¨¡æå¤çé¾è·¯é¢ç?
**Goal**: é¢çå¾ç OCR/è¯­é³ ASR å¤çé¾è·¯ï¼ç»ä¸è¾å¥è¾åºæ ¼å¼

**Independent Test**: ä¸ä¼ å¾çæä»¶ï¼éªè¯?OCR è¯å«åè¿å?HE æåæµç¨

### Implementation

- [x] T030 [US3] å®ç° `document_parser.py` å¤æ¨¡æè·¯ç±ï¼
  - `parse_image(file_path)` â?OCR ææ¬ï¼pytesseract + chi-simï¼?  - OCR è´¨éè¯ä¼°ï¼ä½ç½®ä¿¡åº¦æ è®°ï¼EC-022ï¼?  - ç»ä¸è¾åºæ ¼å¼ï¼`ParsedDocument(text, format, confidence, metadata)`

- [x] T031 [US3] å®ä¹å¤æ¨¡æå¤çé¾è·¯æ¥å£ï¼
  - `MultimodalProcessor` æ½è±¡åºç±»ï¼ABCï¼ï¼
    - `process(file_path) â?ParsedDocument`
    - `supported_formats() â?List[str]`
  - `OCRProcessor(MultimodalProcessor)` â?å¾ç OCR
  - `ASRProcessor(MultimodalProcessor)` â?è¯­é³è½¬æå­ï¼é¢çï¼æä¸å®ç°ï¼
  - å¤çå¨æ³¨åè¡¨ï¼`PROCESSOR_REGISTRY: Dict[str, MultimodalProcessor]`

- [x] T032 [US3] åç«¯å¤æ¨¡æä¸ä¼ æ¯æï¼
  - `DocumentUploader.tsx` æ¯æå¾çæ ¼å¼ï¼?jpg/.png/.tiffï¼?  - ä¸ä¼ å¾çåæç¤?æ­£å¨ OCR è¯å«..."
  - OCR ä½ç½®ä¿¡åº¦æ¶æç¤?è¯å«è´¨éè¾ä½ï¼å»ºè®®äººå·¥æ ¡éª?ï¼EC-022ï¼?
**Checkpoint**: å¾ç OCR å¯ç¨ï¼ASR é¢çæ¥å£ï¼ç»ä¸ I/O æ ¼å¼

---

## Phase 9: US3-AS5 è¡¥å â?èç½æç´¢è¾å©æ¨¡æ¿çæ + AI å©ææ¾æ¸

**Goal**: æ¨¡æ¿ä¸çº§åéä¸­çèç½æç´¢å¨æçæ?+ æåè¿ç¨ä¸?AI å©æè¯¢é®ç®¡çå?
### Implementation

- [x] T033 [US3] å®ç° `template_generator.py` èç½æç´¢å¨æçæï¼
  - `generate_with_web_search(text)` â?è°ç¨ Tavily/DuckDuckGo æç´¢é¢åç¥è¯ â?åºäºæç´¢ç»æçæ HE YAML æ¨¡æ¿
  - æç´¢æå¡ä¸å¯ç¨æ¶éçº§ï¼EC-012ï¼?  - HTML æ¸æ´ï¼å¯¹æç´¢ç»æå?XSS è¿æ»¤ï¼EC-018ï¼?
- [x] T034 [US3] å®ç° AI å©ææ¾æ¸æºå¶ï¼?  - `extraction_service.py` æ°å¢ `_check_ambiguity()` æ¹æ³ï¼åææåç»æä¸­ç½®ä¿¡åº¦ä½çå®ä½?å³ç³»
  - ä½ç½®ä¿¡åº¦å®ä½æ è®°ä¸?`needs_clarification`
  - åç«¯å±ç¤ºæ¾æ¸è¯·æ±ï¼å¼¹çªæ¾ç¤?ä»¥ä¸æ¦å¿µéè¦ç¡®è®?ï¼ç¨æ·ç¡®è®¤åç»§ç»­

- [x] T035 [US3] åç«¯ `TemplateRecommender.tsx` ç»ä»¶ï¼?  - å½ç³»ç»æ æ³èªå¨çææ¨¡æ¿æ¶ï¼å±ç¤ºæ¨èæ¨¡æ¿åè¡?  - æ¯ä¸ªæ¨¡æ¿æ¾ç¤ºåç§°ãæè¿°ãéç¨åºæ¯ãå¹éåº¦
  - ç¨æ·å¯éæ©æ¨èæ¨¡æ¿æèªå®ä¹
  - "èç½æç´¢çæ"æé®ï¼è§¦åå¨ææ¨¡æ¿çæ?
**Checkpoint**: æ¨¡æ¿ä¸çº§åéå®æ´å¯ç¨ï¼AI å©ææ¾æ¸æºå¶å¯ç¨

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: è·¨æäºçæ¹è¿åæ¶å°?
- [x] T036 [P] æ´æ° `odap/web/router_registry.py` â?æ³¨åæ°å¢ç?extraction è·¯ç±ï¼templatesãprovenanceï¼?- [x] T037 [P] æ´æ° `odap/web/app.py` â?ç¡®ä¿æææ°è·¯ç±å¨çäº§å¥å£æ³¨å?- [x] T038 [P] æ´æ°åç«¯ `ontologyApi.ts` â?æ·»å æ?API è°ç¨æ¹æ³ï¼?  - `extractDocument()`ã`extractKB()`ã`listTemplates()`ã`recommendTemplates()`ã`getProvenance()`
- [x] T039 [P] éè¯¯å¤çç»ä¸ â?æææ°è·¯ç±æ·»å  `except HTTPException: raise` éä¼ 
- [x] T040 [P] å®¡è®¡æ¥å¿ â?æåæä½éè¿ `unified_audit.py` è®°å½
- [x] T041 [P] å½éå?â?åç«¯æ°å¢ææ¡æ·»å å?`locales/zh-CN/` å?`locales/en-US/`
- [x] T042 éå»º Docker éå â?`python bootstep.py rebuild main`ï¼éªè¯?HE ä¾èµå®è£æå
- [x] T043 è¿è¡ `quickstart.md` éªè¯ â?ç«¯å°ç«¯éªè¯?NL æåãææ¡£ä¸ä¼ ãç¥è¯åºæåæµç¨
- [x] T044 [REVIEW] ä»£ç å®¡æ¥ â?å¯¹ç§ spec éªæ¶åºæ¯éæ¡éªè¯

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    â?Phase 2 (Foundational) â?BLOCKS ALL
    â?Phase 3 (NL ææ¬æå) â?æ ¸å¿è·¯å¾ï¼ä¼åå®æ?    â?Phase 4 (ææ¡£ä¸ä¼ ) â?ä¾èµ Phase 3 ç?HE éæ
    â?Phase 5 (ç¥è¯åºæå? â?ä¾èµ Phase 3 ç?HE éæ
    â?Phase 6 (é¢è§+æº¯æº+å²çª) â?ä¾èµ Phase 3/4/5 çæåç»æ?    â?Phase 7 (åééåå¥) â?ä¾èµ Phase 6 çç¡®è®¤å¯¼å?    â?Phase 8 (å¤æ¨¡æ? â?å¯ä¸ Phase 6/7 å¹¶è¡
    â?Phase 9 (èç½æç´¢+AIå©æ) â?å¯ä¸ Phase 6/7/8 å¹¶è¡
    â?Phase 10 (Polish) â?ææåè½å®æå
```

### Parallel Opportunities

- **Phase 2 åé¨**: T005/T006/T007/T008/T009 äºä¸ªééå¨å¯å¹¶è¡å¼å?- **Phase 4 vs Phase 5**: ææ¡£ä¸ä¼ åç¥è¯åºæåå¯å¹¶è¡å¼å?- **Phase 8 vs Phase 9**: å¤æ¨¡æåèç½æç´¢å¯å¹¶è¡å¼å?- **Phase 10**: ææ?Polish ä»»å¡å¯å¹¶è¡?
### Within Each Phase

- æµè¯åäºå®ç°ï¼TDD æ è®°çä»»å¡ï¼
- Models â?Services â?Routes â?Frontend
- æ ¸å¿è·¯å¾ä¼åï¼å¢å¼ºåè½åè¡?
---

## Implementation Strategy

### MVP (Phase 1-3)

1. å®æ HE ä¾èµéæåééå±?2. å®æ NL ææ¬æåèµ?HE å¼æ
3. **STOP and VALIDATE**: è¾å¥ä¸æ®µä¸å¡æè¿°ï¼éªè¯ HE æåç»æ
4. å¯æ¼ç¤ºæ ¸å¿æåè½å?
### Incremental Delivery

1. Phase 1-3 â?NL ææ¬æåå¯ç¨ï¼MVPï¼?2. + Phase 4 â?ææ¡£ä¸ä¼ æåå¯ç¨
3. + Phase 5 â?ç¥è¯åºå¢éæåå¯ç?4. + Phase 6 â?é¢è§å¢å¼º+æº¯æº+å²çª
5. + Phase 7 â?åééåå¥
6. + Phase 8-9 â?å¤æ¨¡æ?èç½æç´¢
7. + Phase 10 â?çäº§å°±ç»ª

### Risk Mitigation

- **HE ä¾èµé£é©**: T005 å®ç°éçº§æ¨¡å¼ï¼HE ä¸å¯ç¨æ¶åéå?SchemaLevelExtractor
- **LLM è¶æ¶é£é©**: T011 å®ç°è¶æ¶å¤çåé¨åç»æä¿å­?- **å¤§ææ¡£é£é?*: T007 å®ç°åå+åå¹¶ï¼å¤±è´¥åæ è®°éè¯
- **åééä¸è´æ§é£é?*: T028 å®ç°éé B å¼æ­¥éè¯ï¼ä¸é»å¡éé A
