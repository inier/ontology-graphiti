# Data Model: ODAP 本体驱动分析决策平台

**Branch**: `001-odap-platform` | **Date**: 2026-06-02 | **Plan**: [plan.md](./plan.md)

## 概述

ODAP 采用四引擎存储架构：SQLite（关系型）+ Neo4j（图谱）+ Redis（缓存+会话）+ MinIO（对象存储）。

- **SQLite**: 23 个 DB 文件，60+ 张表，覆盖工作空间/角色/策略/审计/版本/配置等结构化数据
- **Neo4j**: 动态标签节点 + Graphiti 双时态，覆盖本体实例/关系/时序版本/推演结果
- **Redis**: Celery broker/backend + 进程内缓存（GraphManager/OPA），未来扩展分布式缓存
- **MinIO**: 按工作空间分 bucket，存储文档/图片/二进制/导入导出文件

---

## 1. SQLite 数据模型

### 1.1 DB 文件分布

| DB 文件 | 模块 | 表数量 |
|---------|------|--------|
| `ontology_ingest.db` | core/ontology (摄入/版本/文档/构建/验证/场景) | 13 |
| `ontology_core.db` | core/ontology/runtime + core/cognition/thought_graph | 12 |
| `ontology_model.db` | core/ontology/model | 3 |
| `ontology_schema.db` | core/ontology/oms | 2 |
| `ontology_engine.db` | core/ontology/engine | 3 |
| `ontology_session.db` | harness/blueprint/servitization/catalog/memory/shared_memory/graph_sync | 10 |
| `abution_graph.db` | core/ontology/abution_graph | 1 |
| `ingestion_tasks.db` | core/ontology/ingestion | 1 |
| `workspace.db` | platform/workspace | 5 |
| `roles.db` | platform/roles | 6 |
| `skills.db` | platform/skill_system | 1 |
| `sessions.db` | platform/session_memory | 1 |
| `i18n.db` | platform/i18n | 1 |
| `agents.db` | management/agent_management | 1 |
| `business.db` | management/business | 4 |
| `action_records.db` | decision/action_service | 1 |
| `event_simulator.db` | simulation/event_simulator | 3 |
| `simulation_sandbox.db` | simulation/simulation_sandbox | 2 |
| `simulation_deduction.db` | simulation/simulation_deduction | 1 |
| `policy_versions.db` | infra/opa (版本) | 1 |
| `opa_policies.db` | infra/opa (策略) | 1 |
| `audit_v2.db` | infra/security (V2) | 1 |
| `audit.db` | infra/security (通道) | 1 |

### 1.2 核心领域表结构

#### 1.2.1 本体摄入 (ontology_ingest.db)

```sql
CREATE TABLE IF NOT EXISTS ingest_records (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_details TEXT DEFAULT '{}',
    data_schema TEXT DEFAULT '{}',
    record_count INTEGER DEFAULT 0,
    processed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    start_time TEXT,
    end_time TEXT,
    duration_seconds REAL DEFAULT 0,
    errors TEXT DEFAULT '[]',
    quality_metrics TEXT DEFAULT '{}',
    extracted_data TEXT DEFAULT '{}',
    original_content TEXT DEFAULT '',
    created_by TEXT DEFAULT '',
    scenario_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    ingest_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    level TEXT DEFAULT 'info',
    message TEXT DEFAULT '',
    details TEXT DEFAULT '{}',
    actor TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ontology_documents (
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    doc_type TEXT DEFAULT 'standard',
    source TEXT DEFAULT '',
    meta TEXT DEFAULT '{}',
    entities TEXT DEFAULT '[]',
    relations TEXT DEFAULT '[]',
    events TEXT DEFAULT '[]',
    actions TEXT DEFAULT '[]',
    rules TEXT DEFAULT '[]',
    constraints TEXT DEFAULT '[]',
    ontology_version TEXT DEFAULT '',
    scenario_id TEXT DEFAULT '',
    extra_data TEXT DEFAULT '{}',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS build_results (
    id TEXT PRIMARY KEY,
    source_ingest_id TEXT,
    entity_count INTEGER DEFAULT 0,
    relation_count INTEGER DEFAULT 0,
    property_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    start_time TEXT,
    end_time TEXT,
    duration_seconds REAL DEFAULT 0,
    errors TEXT DEFAULT '[]',
    warnings TEXT DEFAULT '[]',
    ontology_version TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ontology_versions (
    id TEXT PRIMARY KEY,
    ontology_id TEXT NOT NULL,
    version_number INTEGER DEFAULT 1,
    parent_version_id TEXT,
    status TEXT DEFAULT 'draft',
    changes TEXT DEFAULT '{}',
    change_summary TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    created_by TEXT DEFAULT '',
    is_current INTEGER DEFAULT 0,
    is_stable INTEGER DEFAULT 0,
    doc_snapshot TEXT DEFAULT '{}',
    doc_id TEXT,
    doc_type TEXT DEFAULT 'standard',
    entity_count INTEGER DEFAULT 0,
    relation_count INTEGER DEFAULT 0,
    event_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS entity_registry (
    canonical_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    name_en TEXT DEFAULT '',
    aliases TEXT DEFAULT '[]',
    ontology_id TEXT DEFAULT '',
    basic_properties TEXT DEFAULT '{}',
    statistical_properties TEXT DEFAULT '{}',
    capabilities TEXT DEFAULT '[]',
    source_doc_id TEXT,
    mention_count INTEGER DEFAULT 0,
    first_seen_at TEXT,
    last_seen_at TEXT,
    confidence REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS validation_results (
    id TEXT PRIMARY KEY,
    ontology_id TEXT NOT NULL,
    ontology_version TEXT DEFAULT '',
    validation_time TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    errors TEXT DEFAULT '[]',
    warnings TEXT DEFAULT '[]',
    info TEXT DEFAULT '[]',
    error_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    info_count INTEGER DEFAULT 0,
    overall_score REAL DEFAULT 0.0,
    duration_seconds REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS process_logs (
    id TEXT PRIMARY KEY,
    ingest_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    operation TEXT NOT NULL,
    details TEXT DEFAULT '{}',
    status TEXT DEFAULT 'running',
    error_message TEXT DEFAULT '',
    duration_ms INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS build_history (
    id TEXT PRIMARY KEY,
    ingest_id TEXT NOT NULL,
    build_id TEXT NOT NULL,
    version_id TEXT,
    document_id TEXT,
    entity_count INTEGER DEFAULT 0,
    relation_count INTEGER DEFAULT 0,
    event_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    start_time TEXT,
    end_time TEXT,
    duration_seconds REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS validation_rules (
    rule_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    rule_type TEXT DEFAULT 'integrity',
    severity TEXT DEFAULT 'warning',
    condition TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS validation_issues (
    issue_id TEXT PRIMARY KEY,
    rule_id TEXT,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'warning',
    ontology_id TEXT DEFAULT '',
    entity_id TEXT DEFAULT '',
    relation_id TEXT DEFAULT '',
    property_name TEXT DEFAULT '',
    message TEXT DEFAULT '',
    details TEXT DEFAULT '{}',
    status TEXT DEFAULT 'open',
    auto_fixable INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    workspace_id TEXT DEFAULT '',
    ontology_id TEXT DEFAULT '',
    current_ontology_version TEXT DEFAULT '',
    doc_count INTEGER DEFAULT 0,
    event_count INTEGER DEFAULT 0,
    entity_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    last_synced TEXT,
    synced_entities TEXT DEFAULT '[]',
    synced_events TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS scenario_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    meta TEXT DEFAULT '{}',
    entities TEXT DEFAULT '[]',
    events TEXT DEFAULT '[]',
    relations TEXT DEFAULT '[]',
    ontology_version TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
```

#### 1.2.2 本体模型 (ontology_model.db)

```sql
CREATE TABLE IF NOT EXISTS entity_types (
    type_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    properties TEXT DEFAULT '[]',
    primary_key TEXT DEFAULT '[]',
    links TEXT DEFAULT '[]',
    actions TEXT DEFAULT '[]',
    constraints TEXT DEFAULT '[]',
    classification_level TEXT DEFAULT 'U',
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS instances (
    instance_id TEXT PRIMARY KEY,
    type_id TEXT NOT NULL,
    properties TEXT DEFAULT '{}',
    workspace_id TEXT DEFAULT 'default',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ontology_documents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT DEFAULT '1.0.0',
    object_types TEXT DEFAULT '[]',
    action_types TEXT DEFAULT '[]',
    relations TEXT DEFAULT '[]',
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
```

#### 1.2.3 本体 OMS (ontology_schema.db)

```sql
CREATE TABLE IF NOT EXISTS object_types (
    type_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    properties TEXT DEFAULT '[]',
    links TEXT DEFAULT '[]',
    actions TEXT DEFAULT '[]',
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    parent_type TEXT,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS action_types (
    action_type_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    target_object_type TEXT DEFAULT '',
    parameters TEXT DEFAULT '[]',
    opa_policy TEXT DEFAULT '',
    required_roles TEXT DEFAULT '[]',
    writeback_config TEXT DEFAULT '{}',
    confirmation_required INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
```

#### 1.2.4 本体运行时 (ontology_core.db)

```sql
CREATE TABLE IF NOT EXISTS ontology_functions (
    function_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    function_type TEXT DEFAULT 'query',
    status TEXT DEFAULT 'draft',
    target_object_type TEXT DEFAULT '',
    input_schema TEXT DEFAULT '{}',
    output_schema TEXT DEFAULT '{}',
    implementation TEXT DEFAULT '{}',
    implementation_type TEXT DEFAULT 'python',
    dependencies TEXT DEFAULT '[]',
    bound_action_contract TEXT,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS action_contracts (
    contract_id TEXT PRIMARY KEY,
    action_type_id TEXT,
    action_name TEXT NOT NULL,
    description TEXT DEFAULT '',
    read_set TEXT DEFAULT '[]',
    write_set TEXT DEFAULT '[]',
    side_effect_set TEXT DEFAULT '[]',
    preconditions TEXT DEFAULT '[]',
    postconditions TEXT DEFAULT '[]',
    is_verified INTEGER DEFAULT 0,
    verified_at TEXT,
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS state_propagation_graphs (
    graph_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    edges TEXT DEFAULT '[]',
    object_types TEXT DEFAULT '[]',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS mutation_records (
    mutation_id TEXT PRIMARY KEY,
    action_type_id TEXT,
    action_name TEXT NOT NULL,
    target_object_id TEXT NOT NULL,
    target_object_type TEXT NOT NULL,
    property_name TEXT DEFAULT '',
    old_value TEXT,
    new_value TEXT,
    mutation_type TEXT DEFAULT 'update',
    timestamp TEXT NOT NULL,
    actor TEXT DEFAULT '',
    scenario_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS world_state_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    object_states TEXT DEFAULT '{}',
    scenario_id TEXT DEFAULT '',
    is_baseline INTEGER DEFAULT 0,
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS aggregate_definitions (
    agg_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    target_object_type TEXT NOT NULL,
    target_property TEXT NOT NULL,
    method TEXT DEFAULT 'sum',
    window TEXT DEFAULT '',
    group_by TEXT DEFAULT '[]',
    output_property TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS action_triggers (
    trigger_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    conditions TEXT DEFAULT '[]',
    action_type_id TEXT,
    action_name TEXT NOT NULL,
    target_object_type TEXT DEFAULT '',
    target_object_id TEXT DEFAULT '',
    parameters TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 0,
    cooldown_seconds INTEGER DEFAULT 0,
    last_fired_at TEXT,
    fire_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS trigger_executions (
    execution_id TEXT PRIMARY KEY,
    trigger_id TEXT NOT NULL,
    action_type_id TEXT,
    action_name TEXT NOT NULL,
    triggered_by TEXT DEFAULT '',
    target_object_id TEXT DEFAULT '',
    target_object_type TEXT DEFAULT '',
    parameters TEXT DEFAULT '{}',
    status TEXT DEFAULT 'pending',
    result TEXT DEFAULT '{}',
    error TEXT DEFAULT '',
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS state_machines (
    sm_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    target_object_type TEXT NOT NULL,
    states TEXT DEFAULT '[]',
    transitions TEXT DEFAULT '[]',
    initial_state TEXT DEFAULT '',
    current_states TEXT DEFAULT '{}',
    bound_action_type_ids TEXT DEFAULT '[]',
    scenario_id TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS thought_nodes (
    thought_id TEXT PRIMARY KEY,
    thought_type TEXT DEFAULT 'observation',
    content TEXT NOT NULL,
    premises TEXT DEFAULT '[]',
    conclusion TEXT DEFAULT '',
    confidence REAL DEFAULT 0.0,
    reasoning_method TEXT DEFAULT 'deductive',
    source_entity_ids TEXT DEFAULT '[]',
    source_scenario_id TEXT DEFAULT '',
    agent_id TEXT DEFAULT '',
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reasoning_chains (
    chain_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    thought_ids TEXT DEFAULT '[]',
    chain_type TEXT DEFAULT 'linear',
    scenario_id TEXT DEFAULT '',
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS thought_edges (
    edge_id TEXT PRIMARY KEY,
    source_thought_id TEXT NOT NULL,
    target_thought_id TEXT NOT NULL,
    edge_type TEXT DEFAULT 'supports',
    weight REAL DEFAULT 1.0,
    metadata TEXT DEFAULT '{}'
);
```

#### 1.2.5 本体引擎 (ontology_engine.db)

```sql
CREATE TABLE IF NOT EXISTS versions (
    version_id TEXT PRIMARY KEY,
    ontology_id TEXT NOT NULL,
    version_number INTEGER DEFAULT 1,
    changelog TEXT DEFAULT '',
    valid_time TEXT,
    transaction_time TEXT,
    status TEXT DEFAULT 'draft',
    snapshot TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS audit_records (
    audit_id TEXT PRIMARY KEY,
    entity_type_id TEXT,
    source TEXT DEFAULT '',
    process_steps TEXT DEFAULT '[]',
    transform_rules TEXT DEFAULT '[]',
    result TEXT DEFAULT '{}',
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_audit_records (
    audit_id TEXT PRIMARY KEY,
    entity_type_id TEXT,
    source TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    process_steps TEXT DEFAULT '[]',
    transform_rules TEXT DEFAULT '[]',
    result TEXT DEFAULT '{}',
    timestamp TEXT NOT NULL
);
```

#### 1.2.6 本体摄入任务 (ingestion_tasks.db)

```sql
CREATE TABLE IF NOT EXISTS ingest_tasks (
    task_id TEXT PRIMARY KEY,
    workspace_id TEXT DEFAULT 'default',
    file_name TEXT DEFAULT '',
    file_type TEXT DEFAULT '',
    storage_key TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    source TEXT DEFAULT 'upload',
    process_steps TEXT DEFAULT '[]',
    transform_rules TEXT DEFAULT '[]',
    extracted_text TEXT DEFAULT '',
    extracted_tables TEXT DEFAULT '[]',
    error_message TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
```

#### 1.2.7 Harness/Blueprint/服务化/记忆 (ontology_session.db)

```sql
CREATE TABLE IF NOT EXISTS harness_sessions (
    session_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    current_stage TEXT DEFAULT 'requirement',
    stage_results TEXT DEFAULT '{}',
    hitl_confirmations TEXT DEFAULT '[]',
    agent_tasks TEXT DEFAULT '[]',
    context_memory TEXT DEFAULT '{}',
    scenario_id TEXT DEFAULT '',
    workspace_id TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    requirement TEXT DEFAULT '{}',
    sub_tasks TEXT DEFAULT '[]',
    messages TEXT DEFAULT '[]',
    planning_output TEXT DEFAULT '{}',
    ontology_output TEXT DEFAULT '{}',
    execution_output TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS ontology_blueprints (
    blueprint_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    nodes TEXT DEFAULT '[]',
    edges TEXT DEFAULT '[]',
    session_id TEXT,
    version TEXT DEFAULT '1.0.0',
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS blueprint_designs (
    blueprint_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    scenario_id TEXT DEFAULT '',
    version TEXT DEFAULT '1.0.0',
    nodes TEXT DEFAULT '[]',
    edges TEXT DEFAULT '[]',
    layout TEXT DEFAULT '{}',
    is_published INTEGER DEFAULT 0,
    parent_version_id TEXT,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS skill_templates (
    template_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    service_type TEXT DEFAULT 'api',
    object_type TEXT DEFAULT '',
    function_mappings TEXT DEFAULT '[]',
    parameter_schema TEXT DEFAULT '{}',
    output_schema TEXT DEFAULT '{}',
    code_template TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS generated_services (
    service_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    service_type TEXT DEFAULT 'api',
    source_ontology_id TEXT,
    source_object_type TEXT DEFAULT '',
    source_function_ids TEXT DEFAULT '[]',
    template_id TEXT,
    code TEXT DEFAULT '',
    parameter_schema TEXT DEFAULT '{}',
    output_schema TEXT DEFAULT '{}',
    endpoint_path TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    version TEXT DEFAULT '1.0.0',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS service_deployments (
    deployment_id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL,
    endpoint_url TEXT DEFAULT '',
    deployed_at TEXT,
    is_active INTEGER DEFAULT 0,
    health_status TEXT DEFAULT 'unknown',
    last_health_check TEXT
);

CREATE TABLE IF NOT EXISTS service_catalog (
    catalog_id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL,
    service_name TEXT NOT NULL,
    service_type TEXT DEFAULT 'api',
    source_ontology_id TEXT,
    source_object_type TEXT DEFAULT '',
    source_ontology_version TEXT DEFAULT '',
    current_version TEXT DEFAULT '1.0.0',
    status TEXT DEFAULT 'active',
    capabilities TEXT DEFAULT '[]',
    endpoint_path TEXT DEFAULT '',
    description TEXT DEFAULT '',
    registered_at TEXT DEFAULT '',
    last_updated_at TEXT DEFAULT '',
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS service_version_links (
    link_id TEXT PRIMARY KEY,
    catalog_id TEXT NOT NULL,
    ontology_version_id TEXT DEFAULT '',
    service_version TEXT DEFAULT '',
    is_compatible INTEGER DEFAULT 1,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS memory_entries (
    memory_id TEXT PRIMARY KEY,
    memory_type TEXT DEFAULT 'episodic',
    content TEXT NOT NULL,
    summary TEXT DEFAULT '',
    keywords TEXT DEFAULT '[]',
    entities TEXT DEFAULT '[]',
    source_scenario_id TEXT DEFAULT '',
    source_session_id TEXT DEFAULT '',
    importance REAL DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    decay_factor REAL DEFAULT 1.0,
    embedding TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    last_accessed_at TEXT,
    expires_at TEXT,
    status TEXT DEFAULT 'active',
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS memory_consolidations (
    consolidation_id TEXT PRIMARY KEY,
    source_ids TEXT DEFAULT '[]',
    result_id TEXT,
    strategy TEXT DEFAULT 'merge',
    summary TEXT DEFAULT '',
    importance REAL DEFAULT 0.5,
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS shared_contexts (
    context_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    scenario_id TEXT DEFAULT '',
    session_id TEXT DEFAULT '',
    shared_state TEXT DEFAULT '{}',
    version INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS agent_states (
    state_id TEXT PRIMARY KEY,
    context_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    agent_role TEXT DEFAULT '',
    state_data TEXT DEFAULT '{}',
    last_heartbeat TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS shared_events (
    event_id TEXT PRIMARY KEY,
    context_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT DEFAULT '{}',
    target_agent_id TEXT DEFAULT '',
    is_consumed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS memory_graph_sync_map (
    sync_id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL,
    graph_entity_id TEXT DEFAULT '',
    graph_episode_name TEXT DEFAULT '',
    sync_type TEXT DEFAULT 'memory_to_graph',
    sync_status TEXT DEFAULT 'pending',
    last_synced_at TEXT,
    metadata TEXT DEFAULT '{}'
);
```

#### 1.2.8 Abution 图 (abution_graph.db)

```sql
CREATE TABLE IF NOT EXISTS abution_graph_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    temporal_nodes TEXT DEFAULT '[]',
    pattern_nodes TEXT DEFAULT '[]',
    force_nodes TEXT DEFAULT '[]',
    action_nodes TEXT DEFAULT '[]',
    cross_dimension_links TEXT DEFAULT '[]',
    created_at TEXT DEFAULT ''
);
```

### 1.3 平台领域表结构

#### 1.3.1 工作空间 (workspace.db)

```sql
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    type TEXT DEFAULT 'default',
    status TEXT DEFAULT 'active',
    owner TEXT DEFAULT '',
    members TEXT DEFAULT '[]',
    config TEXT DEFAULT '{}',
    tags TEXT DEFAULT '[]',
    resources TEXT DEFAULT '{}',
    bound_ontology_ids TEXT DEFAULT '[]',
    last_accessed_at TEXT,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS isolation_policies (
    workspace_id TEXT PRIMARY KEY,
    isolation_level TEXT DEFAULT 'standard',
    resource_quota TEXT DEFAULT '{}',
    network_policy TEXT DEFAULT '{}',
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS import_export_records (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    source TEXT DEFAULT '',
    destination TEXT DEFAULT '',
    progress REAL DEFAULT 0.0,
    file_size INTEGER DEFAULT 0,
    errors TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    start_time TEXT,
    end_time TEXT,
    duration_seconds REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    workspace_id TEXT NOT NULL,
    ontology_id TEXT DEFAULT '',
    current_ontology_version TEXT DEFAULT '',
    doc_count INTEGER DEFAULT 0,
    event_count INTEGER DEFAULT 0,
    entity_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS scenario_ontology_bindings (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    ontology_id TEXT NOT NULL,
    binding_status TEXT DEFAULT 'active',
    bound_by TEXT DEFAULT '',
    bound_at TEXT DEFAULT '',
    unbound_at TEXT
);
```

#### 1.3.2 角色 (roles.db)

```sql
CREATE TABLE IF NOT EXISTS permissions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    scope TEXT DEFAULT 'global',
    actions TEXT DEFAULT '[]',
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    role_type TEXT DEFAULT 'custom',
    permissions TEXT DEFAULT '[]',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id TEXT NOT NULL,
    permission_id TEXT NOT NULL,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS role_skills (
    role_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    PRIMARY KEY (role_id, skill_id)
);

CREATE TABLE IF NOT EXISTS role_policies (
    role_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    PRIMARY KEY (role_id, policy_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    workspace_id TEXT DEFAULT '',
    bound_at TEXT DEFAULT '',
    bound_by TEXT DEFAULT ''
);
```

#### 1.3.3 技能 (skills.db)

```sql
CREATE TABLE IF NOT EXISTS skills (
    skill_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT DEFAULT 'general',
    skill_type TEXT DEFAULT 'python',
    status TEXT DEFAULT 'draft',
    description TEXT DEFAULT '',
    path TEXT DEFAULT '',
    files TEXT DEFAULT '[]',
    enabled INTEGER DEFAULT 1,
    version TEXT DEFAULT '1.0.0',
    input_schema TEXT DEFAULT '{}',
    output_schema TEXT DEFAULT '{}',
    triggers TEXT DEFAULT '[]',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
```

#### 1.3.4 会话 (sessions.db)

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT DEFAULT 'default',
    title TEXT DEFAULT '',
    messages TEXT DEFAULT '[]',
    context_window TEXT DEFAULT '{}',
    cot_tree_data TEXT DEFAULT '{}',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1
);
```

#### 1.3.5 国际化 (i18n.db)

```sql
CREATE TABLE IF NOT EXISTS translations (
    key TEXT NOT NULL,
    module TEXT NOT NULL,
    locale TEXT NOT NULL,
    value TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    PRIMARY KEY (key, module, locale)
);
```

### 1.4 管理领域表结构

#### 1.4.1 Agent 管理 (agents.db)

```sql
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    avatar TEXT DEFAULT '',
    description TEXT DEFAULT '',
    main_object TEXT DEFAULT '',
    related_objects TEXT DEFAULT '[]',
    related_processes TEXT DEFAULT '[]',
    related_rules TEXT DEFAULT '[]',
    related_business_logic TEXT DEFAULT '[]',
    related_indicators TEXT DEFAULT '[]',
    related_skills TEXT DEFAULT '[]',
    related_knowledge_bases TEXT DEFAULT '[]',
    allowed_roles TEXT DEFAULT '[]',
    workspace_id TEXT DEFAULT '',
    created_by TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
```

#### 1.4.2 业务 (business.db)

```sql
CREATE TABLE IF NOT EXISTS business_processes (
    process_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    related_objects TEXT DEFAULT '[]',
    related_processes TEXT DEFAULT '[]',
    related_rules TEXT DEFAULT '[]',
    related_logics TEXT DEFAULT '[]',
    related_indicators TEXT DEFAULT '[]',
    llm_description TEXT DEFAULT '',
    flow_nodes TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft',
    created_by TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    yaml_definition TEXT DEFAULT '',
    ontology_id TEXT DEFAULT '',
    version_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS business_rules (
    rule_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    related_objects TEXT DEFAULT '[]',
    related_processes TEXT DEFAULT '[]',
    related_rules TEXT DEFAULT '[]',
    related_logics TEXT DEFAULT '[]',
    related_indicators TEXT DEFAULT '[]',
    llm_description TEXT DEFAULT '',
    rule_conditions TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft',
    created_by TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    yaml_definition TEXT DEFAULT '',
    ontology_id TEXT DEFAULT '',
    version_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS business_logics (
    logic_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    related_objects TEXT DEFAULT '[]',
    related_processes TEXT DEFAULT '[]',
    related_rules TEXT DEFAULT '[]',
    related_logics TEXT DEFAULT '[]',
    related_indicators TEXT DEFAULT '[]',
    llm_description TEXT DEFAULT '',
    logic_type TEXT DEFAULT 'condition',
    logic_expression TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    created_by TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    yaml_definition TEXT DEFAULT '',
    ontology_id TEXT DEFAULT '',
    version_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS business_indicators (
    indicator_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    related_objects TEXT DEFAULT '[]',
    related_processes TEXT DEFAULT '[]',
    related_rules TEXT DEFAULT '[]',
    related_logics TEXT DEFAULT '[]',
    related_indicators TEXT DEFAULT '[]',
    llm_description TEXT DEFAULT '',
    indicator_type TEXT DEFAULT 'quantitative',
    calculation_formula TEXT DEFAULT '',
    unit TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    created_by TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    yaml_definition TEXT DEFAULT '',
    ontology_id TEXT DEFAULT '',
    version_id TEXT DEFAULT ''
);
```

### 1.5 决策领域表结构

#### 1.5.1 动作记录 (action_records.db)

```sql
CREATE TABLE IF NOT EXISTS action_records (
    action_record_id TEXT PRIMARY KEY,
    action_type_id TEXT NOT NULL,
    target_object_id TEXT NOT NULL,
    target_object_type TEXT NOT NULL,
    parameters TEXT DEFAULT '{}',
    status TEXT DEFAULT 'pending',
    requested_by TEXT DEFAULT '',
    reason TEXT DEFAULT '',
    agent_id TEXT DEFAULT '',
    opa_decision TEXT DEFAULT '{}',
    validation_result TEXT DEFAULT '{}',
    execution_result TEXT DEFAULT '{}',
    writeback_result TEXT DEFAULT '{}',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
```

### 1.6 模拟领域表结构

#### 1.6.1 事件模拟器 (event_simulator.db)

```sql
CREATE TABLE IF NOT EXISTS event_templates (
    template_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    event_types TEXT DEFAULT '[]',
    entity_types TEXT DEFAULT '[]',
    config TEXT DEFAULT '{}',
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS event_sequences (
    sequence_id TEXT PRIMARY KEY,
    template_id TEXT,
    workspace_id TEXT DEFAULT 'default',
    events TEXT DEFAULT '[]',
    total_events INTEGER DEFAULT 0,
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS timelines (
    timeline_id TEXT PRIMARY KEY,
    clock_state TEXT DEFAULT 'stopped',
    start_time TEXT,
    current_time TEXT,
    speed REAL DEFAULT 1.0,
    events TEXT DEFAULT '[]',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
```

#### 1.6.2 模拟沙箱 (simulation_sandbox.db)

```sql
CREATE TABLE IF NOT EXISTS sandboxes (
    sandbox_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'created',
    config TEXT DEFAULT '{}',
    isolation_level TEXT DEFAULT 'standard',
    created_at TEXT DEFAULT '',
    started_at TEXT,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS sandbox_results (
    sandbox_id TEXT PRIMARY KEY,
    risk_assessment TEXT DEFAULT '{}',
    metric_changes TEXT DEFAULT '{}',
    recommendations TEXT DEFAULT '[]',
    summary TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
```

#### 1.6.3 模拟推演 (simulation_deduction.db)

```sql
CREATE TABLE IF NOT EXISTS deduction_scenarios (
    scenario_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    source_recommendation_id TEXT,
    source_analysis_id TEXT,
    target_object_id TEXT DEFAULT '',
    target_object_type TEXT DEFAULT '',
    baseline_metrics TEXT DEFAULT '{}',
    available_conditions TEXT DEFAULT '[]',
    chains TEXT DEFAULT '[]',
    results TEXT DEFAULT '{}',
    status TEXT DEFAULT 'draft',
    best_chain_id TEXT,
    tags TEXT DEFAULT '[]',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
```

### 1.7 基础设施层表结构

#### 1.7.1 OPA 策略 (opa_policies.db)

```sql
CREATE TABLE IF NOT EXISTS policies (
    policy_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    status TEXT DEFAULT 'active',
    version INTEGER DEFAULT 1,
    markdown_content TEXT DEFAULT '',
    rego_content TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
```

#### 1.7.2 OPA 策略版本 (policy_versions.db)

```sql
CREATE TABLE IF NOT EXISTS policy_versions (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    rego_text TEXT DEFAULT '',
    markdown_text TEXT DEFAULT '',
    version INTEGER DEFAULT 1,
    status TEXT DEFAULT 'draft',
    created_at TEXT DEFAULT '',
    compiled_at TEXT
);
```

#### 1.7.3 审计日志 V2 (audit_v2.db)

```sql
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    actor_id TEXT DEFAULT '',
    actor_name TEXT DEFAULT '',
    action TEXT NOT NULL,
    resource_type TEXT DEFAULT '',
    resource_id TEXT DEFAULT '',
    result TEXT DEFAULT '',
    message TEXT DEFAULT '',
    workspace_id TEXT DEFAULT '',
    trace_id TEXT DEFAULT '',
    parent_event_id TEXT,
    duration_ms INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    previous_hash TEXT DEFAULT '',
    current_hash TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
```

#### 1.7.4 审计通道 (audit.db)

```sql
CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    actor_type TEXT DEFAULT 'user',
    actor_id TEXT DEFAULT '',
    actor_name TEXT DEFAULT '',
    action TEXT NOT NULL,
    resource_type TEXT DEFAULT '',
    resource_id TEXT DEFAULT '',
    result_status TEXT DEFAULT '',
    result_message TEXT DEFAULT '',
    workspace_id TEXT DEFAULT '',
    trace_id TEXT DEFAULT '',
    parent_event_id TEXT,
    duration_ms INTEGER DEFAULT 0,
    context TEXT DEFAULT '{}',
    changes TEXT DEFAULT '{}',
    checksum TEXT DEFAULT ''
);
```

### 1.8 SQLite 通用规则

| 规则 | 说明 |
|------|------|
| 连接管理 | 每次操作 `sqlite3.connect()` → 用完 `conn.close()`，无连接池 |
| 复杂字段 | Dict/List/Set → JSON TEXT 列 |
| 枚举存储 | Enum → `.value` 字符串存储 |
| 时间存储 | datetime → ISO 8601 字符串存储 |
| 工作空间隔离 | workspace_id 过滤（非分表） |
| 主键策略 | UUID4 字符串（`str(uuid.uuid4())`） |
| Upsert | `INSERT OR REPLACE` 模式 |

---

## 2. Neo4j 数据模型

### 2.1 节点标签

| 标签 | 说明 | 关键属性 |
|------|------|---------|
| `Entity` | 通用实体基标签 | `id` (UNIQUE), `name`, `workspace_id`, `valid_time`, `transaction_time` |
| `Entity:{Type}` | 动态子标签（如 `Entity:Location`） | 继承 Entity + 类型特有属性 |
| `AuditLog` | 审计日志节点 | `id`, `name`, `action`, `workspace_id` |
| `AuditUser` | 审计用户节点 | `id`, `workspace_id` |

### 2.2 唯一性约束

```cypher
CREATE CONSTRAINT entity_id IF NOT EXISTS
FOR (e:Entity) REQUIRE e.id IS UNIQUE;
```

### 2.3 关系类型

| 关系类型 | 说明 | 属性 |
|---------|------|------|
| `RELATES_TO` | 通用关联 | `source_node_uuid`, `target_node_uuid` |
| `{DYNAMIC}` | 业务层动态生成 | 大写+下划线化（如 `TRACKS`, `LOCATED_AT`） |

### 2.4 Graphiti 集成模式

Graphiti SDK 通过 Episode 机制写入图谱：

```python
graph.add_episode(
    name="episode_name",
    episode_body="natural language description",
    source_description="source info",
    reference_time=datetime.now()
)
```

Graphiti 内部自动生成：
- `Entity` 节点 + `EpisodicNode` + `CommunityNode`
- 双时态属性：`valid_time` + `transaction_time`

### 2.5 工作空间隔离

所有节点必须包含 `workspace_id` 属性，查询时按工作空间过滤：

```cypher
MATCH (e:Entity {workspace_id: $workspace_id})
WHERE e.valid_time <= $valid_time
RETURN e
```

---

## 3. Redis 数据模型

### 3.1 当前使用

| 用途 | Key 模式 | TTL | 说明 |
|------|---------|-----|------|
| Celery Broker | `redis://localhost:6379/0` | — | 消息队列 |
| Celery Backend | `redis://localhost:6379/0` | — | 任务结果 |

### 3.2 进程内缓存（替代 Redis）

#### GraphManager 查询缓存

| 缓存键模式 | 生成方式 | TTL | 容量 |
|-----------|---------|-----|------|
| `qe\|area={area}\|entity_type={type}\|workspace_id={ws}` | 实体查询结果 | 5min | 256 项 |
| `qt\|entity_type={type}\|transaction_time={tt}\|valid_time={vt}` | 时态查询结果 | 5min | 256 项 |

#### OPA 策略缓存

| 缓存键模式 | 生成方式 | TTL | 容量 |
|-----------|---------|-----|------|
| `hash(user_id + user_roles + action + resource + workspace_id)` | 策略决策结果 | 可配置 | 可配置 |

### 3.3 未来扩展规划

| 用途 | Key 模式 | TTL | 说明 |
|------|---------|-----|------|
| 短期记忆 | `odap:{ws}:memory:short:{session_id}` | 30min | 对话上下文 |
| 工作记忆 | `odap:{ws}:memory:working:{session_id}` | 2h | 当前任务状态 |
| 查询缓存 | `odap:{ws}:query:cache:{hash}` | 5min | 分布式查询缓存 |
| 策略缓存 | `odap:{ws}:opa:cache:{hash}` | 30s | OPA 决策缓存 |
| 会话状态 | `odap:{ws}:session:{session_id}` | 24h | 用户会话 |

---

## 4. MinIO 数据模型

### 4.1 Bucket 策略

| Bucket 命名 | 说明 | 版本控制 |
|------------|------|---------|
| `ws-{workspace_id}` | 每个工作空间一个 bucket | 启用 |

### 4.2 对象 Key 规范

```
{module}/{entity_type}/{entity_id}/{filename}
```

示例：
- `ingestion/pdf/report-2024/analysis.pdf`
- `ontology/export/workspace-1/backup.json`
- `simulation/results/sandbox-abc/metrics.csv`

### 4.3 预签名 URL

| 参数 | 值 |
|------|-----|
| 有效期 | 1 小时 |
| 用途 | 临时文件访问、上传下载 |

---

## 5. 跨引擎数据关联

### 5.1 核心实体关联图

```
SQLite (workspaces) ──workspace_id──→ Neo4j (Entity.workspace_id)
       │                                    │
       ├── scenarios ──ontology_id──→ SQLite (ontology_versions)
       │                                    │
       └── scenario_ontology_bindings       └── Neo4j (Entity via scenario filter)

SQLite (agents) ──workspace_id──→ SQLite (workspaces)
       │
       └── allowed_roles ──role_id──→ SQLite (roles)

SQLite (action_records) ──action_type_id──→ SQLite (action_types)
       │                                         │
       └── target_object_id ──→ Neo4j (Entity.id)

SQLite (memory_entries) ──memory_id──→ memory_graph_sync_map ──→ Neo4j (Entity.id)
```

### 5.2 数据一致性保证

| 场景 | 策略 |
|------|------|
| SQLite 写入失败 | 回滚事务，不写入 Neo4j |
| Neo4j 写入失败 | 仅 log 警告，SQLite 记录保留（降级不回滚） |
| MinIO 上传失败 | 返回错误，不创建 SQLite 记录 |
| 跨引擎查询 | 以 SQLite 为权威源，Neo4j 为增强源 |

---

## 6. 索引设计

### 6.1 SQLite 索引

```sql
CREATE INDEX IF NOT EXISTS idx_ingest_records_status ON ingest_records(status);
CREATE INDEX IF NOT EXISTS idx_ingest_records_scenario ON ingest_records(scenario_id);
CREATE INDEX IF NOT EXISTS idx_ontology_versions_ontology ON ontology_versions(ontology_id);
CREATE INDEX IF NOT EXISTS idx_ontology_versions_current ON ontology_versions(ontology_id, is_current);
CREATE INDEX IF NOT EXISTS idx_entity_registry_type ON entity_registry(entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_registry_name ON entity_registry(name);
CREATE INDEX IF NOT EXISTS idx_instances_type ON instances(type_id);
CREATE INDEX IF NOT EXISTS idx_instances_workspace ON instances(workspace_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_workspace ON scenarios(workspace_id);
CREATE INDEX IF NOT EXISTS idx_workspaces_status ON workspaces(status);
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_workspace ON user_roles(workspace_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor ON audit_events(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_workspace ON audit_events(workspace_id);
CREATE INDEX IF NOT EXISTS idx_memory_entries_type ON memory_entries(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_entries_scenario ON memory_entries(source_scenario_id);
CREATE INDEX IF NOT EXISTS idx_action_records_status ON action_records(status);
CREATE INDEX IF NOT EXISTS idx_action_records_target ON action_records(target_object_id);
CREATE INDEX IF NOT EXISTS idx_mutations_target ON mutation_records(target_object_id);
CREATE INDEX IF NOT EXISTS idx_mutations_timestamp ON mutation_records(timestamp);
```

### 6.2 Neo4j 索引

```cypher
CREATE CONSTRAINT entity_id IF NOT EXISTS
FOR (e:Entity) REQUIRE e.id IS UNIQUE;

CREATE INDEX entity_workspace IF NOT EXISTS
FOR (e:Entity) ON (e.workspace_id);
```cypher
CREATE INDEX entity_valid_time IF NOT EXISTS
FOR (e:Entity) ON (e.valid_time);
```

---

## Phase 4 增量数据模型 (2026-06-05 Brainstorm)

> 以下数据模型对应 plan.md "Phase 4: Palantir/OntoFlow 增强层"。

### 7. Data Health 数据模型 (FR-031)

#### 7.1 SQLite Schema

新增 `ontology_health.db`：

```sql
-- 健康规则
CREATE TABLE IF NOT EXISTS health_rules (
    id TEXT PRIMARY KEY,                     -- uuid
    target_type_id TEXT NOT NULL,            -- 目标 ObjectType ID
    rule_name TEXT NOT NULL,
    check_expression TEXT NOT NULL,          -- JSON/YAML 声明式规则
    severity TEXT NOT NULL,                  -- info/warning/error/critical
    schedule TEXT,                            -- cron 表达式
    notification_channel TEXT,                -- email/webhook/im (JSON)
    is_enabled INTEGER NOT NULL DEFAULT 1,
    last_scan_at TEXT,                        -- ISO datetime
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_health_rules_target ON health_rules(target_type_id);
CREATE INDEX IF NOT EXISTS idx_health_rules_enabled ON health_rules(is_enabled);

-- 健康报告
CREATE TABLE IF NOT EXISTS health_reports (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    instance_id TEXT NOT NULL,
    instance_type_id TEXT NOT NULL,
    status TEXT NOT NULL,                     -- pass/warn/fail
    details TEXT,                             -- JSON details
    detected_at TEXT NOT NULL,
    is_resolved INTEGER NOT NULL DEFAULT 0,
    resolved_at TEXT,
    resolved_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_health_reports_rule ON health_reports(rule_id);
CREATE INDEX IF NOT EXISTS idx_health_reports_instance ON health_reports(instance_id);
CREATE INDEX IF NOT EXISTS idx_health_reports_status ON health_reports(status);

-- 扫描任务
CREATE TABLE IF NOT EXISTS health_scan_jobs (
    id TEXT PRIMARY KEY,
    rule_id TEXT,                              -- NULL 表示全量扫描
    scan_type TEXT NOT NULL,                   -- full/incremental
    status TEXT NOT NULL,                      -- pending/running/completed/failed
    started_at TEXT NOT NULL,
    completed_at TEXT,
    progress INTEGER DEFAULT 0,                -- 0-100
    total_count INTEGER,
    scanned_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_health_scan_jobs_status ON health_scan_jobs(status);
```

#### 7.2 规则表达式样例 (YAML)

```yaml
# 完整性规则：Equipment 的 currentLocation 必须非空
rule:
  name: "Equipment currentLocation required"
  type: completeness
  target: Equipment
  when: "status == 'ACTIVE'"
  check: "currentLocation IS NOT NULL"
  severity: error

# 一致性规则：Order 关联的 Customer 必须存在
rule:
  name: "Order customer exists"
  type: referential
  target: Order
  check: "customer_id IN (SELECT id FROM Customer)"
  severity: error

# 漂移规则：旧版本 schema 已删除的字段不应再出现
rule:
  name: "Field deprecated_xyz should not exist"
  type: drift
  target: Equipment
  check: "NOT has_property('deprecated_xyz')"
  severity: warning
```

### 8. 本体 Branch & Merge 数据模型 (FR-032)

#### 8.1 SQLite Schema

新增 `ontology_branches.db`：

```sql
-- 分支
CREATE TABLE IF NOT EXISTS ontology_branches (
    id TEXT PRIMARY KEY,
    ontology_id TEXT NOT NULL,
    name TEXT NOT NULL,                       -- main / feature/team-x
    base_version_id TEXT,
    head_version_id TEXT,
    is_protected INTEGER NOT NULL DEFAULT 0,
    merge_strategy TEXT NOT NULL DEFAULT 'auto', -- auto/manual/3-way
    created_at TEXT NOT NULL,
    created_by TEXT,
    UNIQUE(ontology_id, name)
);
CREATE INDEX IF NOT EXISTS idx_branches_ontology ON ontology_branches(ontology_id);

-- 合并请求
CREATE TABLE IF NOT EXISTS merge_requests (
    id TEXT PRIMARY KEY,
    source_branch_id TEXT NOT NULL,
    target_branch_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'open',      -- open/merged/conflicted/closed
    diff TEXT,                                 -- JSON Patch
    conflicts TEXT,                            -- JSON array of Conflict
    created_at TEXT NOT NULL,
    created_by TEXT,
    merged_at TEXT,
    merged_by TEXT,
    goal_id TEXT                               -- FR-036 OntoFlow 关联
);
CREATE INDEX IF NOT EXISTS idx_mr_status ON merge_requests(status);
CREATE INDEX IF NOT EXISTS idx_mr_source ON merge_requests(source_branch_id);
CREATE INDEX IF NOT EXISTS idx_mr_target ON merge_requests(target_branch_id);

-- MR 审批人
CREATE TABLE IF NOT EXISTS mr_reviewers (
    mr_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,                        -- reviewer/approver/observer
    status TEXT NOT NULL DEFAULT 'pending',   -- pending/approved/rejected
    reviewed_at TEXT,
    comment TEXT,
    PRIMARY KEY(mr_id, user_id)
);

-- 冲突解决记录
CREATE TABLE IF NOT EXISTS conflict_resolutions (
    id TEXT PRIMARY KEY,
    mr_id TEXT NOT NULL,
    field_path TEXT NOT NULL,
    resolution TEXT NOT NULL,                  -- ours/theirs/manual
    resolved_value TEXT,                       -- JSON
    resolved_at TEXT NOT NULL,
    resolved_by TEXT
);
```

### 9. Object Type 继承 + Mixin 数据模型 (FR-033)

```python
class Mixin(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    properties: List[Property] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    is_abstract: bool = False

class EntityType(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    inherits: List[str] = Field(default_factory=list)   # 父类 EntityType IDs
    mixins: List[str] = Field(default_factory=list)     # Mixin IDs
    properties: List[Property] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    primary_key: List[str] = Field(default_factory=list)
    constraints: List[Constraint] = Field(default_factory=list)
    
    @property
    def effective_properties(self) -> List[Property]:
        """解析继承链 + mixin，返回扁平化的属性列表"""
        # 1. 收集所有父类的 properties (递归，最深 5 层)
        # 2. 收集所有 mixin 的 properties
        # 3. 去重（同名字段，子类 override 父类）
        ...
```

### 10. Action Type 数据模型 (FR-034)

新增 `ontology_action_types.db`：

```sql
CREATE TABLE IF NOT EXISTS action_types (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    target_entity_type_id TEXT,
    parameters TEXT NOT NULL,                   -- JSON: List[ActionParam]
    return_type TEXT,                            -- JSON: ActionReturn
    implementation TEXT NOT NULL,                -- JSON: List[SkillBinding]
    preconditions TEXT,                          -- JSON: List[OPA 策略]
    postconditions TEXT,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_action_types_target ON action_types(target_entity_type_id);

CREATE TABLE IF NOT EXISTS action_executions (
    id TEXT PRIMARY KEY,
    action_type_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    arguments TEXT,
    status TEXT NOT NULL,                        -- running/success/failed/rolled_back
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT,
    skill_results TEXT
);
CREATE INDEX IF NOT EXISTS idx_action_exec_action ON action_executions(action_type_id);
CREATE INDEX IF NOT EXISTS idx_action_exec_status ON action_executions(status);
```

### 11. 计算属性 + 物化视图数据模型 (FR-035)

```python
class Property(BaseModel):
    name: str
    data_type: str
    is_computed: bool = False
    depends_on: List[str] = Field(default_factory=list)
    compute_expression: Optional[str] = None
    cache_strategy: Literal["none", "lazy", "eager", "hybrid"] = "eager"
    materialize_view: Optional[str] = None
```

```sql
CREATE TABLE IF NOT EXISTS materialized_views (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    target_entity_type_id TEXT NOT NULL,
    computed_property TEXT NOT NULL,
    depends_on_paths TEXT NOT NULL,
    refresh_strategy TEXT NOT NULL,
    schedule TEXT,
    status TEXT NOT NULL,                       -- active/degraded/disabled
    last_refresh_at TEXT,
    next_refresh_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS materialized_view_cache (
    view_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    value TEXT,
    computed_at TEXT NOT NULL,
    is_stale INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(view_id, entity_id)
);
```

### 12. OntoFlow Goal 数据模型 (FR-036)

```sql
CREATE TABLE IF NOT EXISTS ontology_goals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    rationale TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'active',
    linked_requirements TEXT,
    target_ontology_id TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT,
    achieved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_goals_status ON ontology_goals(status);

-- 在 ontology_changes 表添加 goal_id 字段 (强制 NOT NULL)
ALTER TABLE ontology_changes ADD COLUMN goal_id TEXT NOT NULL DEFAULT '';
ALTER TABLE ontology_changes ADD COLUMN rationale TEXT NOT NULL DEFAULT '';
```

### 13. Object View 数据模型 (FR-037)

```sql
CREATE TABLE IF NOT EXISTS object_views (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    target_entity_type_id TEXT NOT NULL,
    included_properties TEXT NOT NULL,
    included_actions TEXT,
    role_binding TEXT,
    redaction_rules TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(target_entity_type_id, name)
);

CREATE TABLE IF NOT EXISTS view_resolution_cache (
    view_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    resolved_properties TEXT NOT NULL,
    resolved_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY(view_id, user_id, entity_id)
);
```

```python
class RedactionType(str, Enum):
    MASK = "mask"
    HASH = "hash"
    PARTIAL = "partial"
    REMOVE = "remove"

class RedactionRule(BaseModel):
    field_path: str
    redaction_type: RedactionType
    params: Dict[str, Any] = Field(default_factory=dict)
```已知问题与改进方向

| 问题 | 影响 | 改进建议 |
|------|------|---------|
| `ontology_session.db` 被 7 个存储类共享 | 表名冲突风险 | 按子模块拆分为独立 DB |
| `ontology_core.db` 被 3 个模块共享 | 并发写入瓶颈 | runtime/state_machine/thought_graph 分离 |
| 审计表存在两套 Schema | 数据不一致 | 统一为 V2 版本，废弃 Channel 版本 |
| Redis 未深度集成 | 分布式缓存缺失 | 迁移进程内缓存到 Redis |
| SQLite 无连接池 | 高并发下性能受限 | 引入 `aiosqlite` 异步连接 |
| 部分路由内联 Schema | 不可复用 | 统一提取到 `schemas.py` |
