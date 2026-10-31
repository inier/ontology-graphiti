import { useState, useEffect } from 'react';

import { Tabs, message } from 'antd';

import { api } from '@/modules/shared/services/api';

import { useScenario, useWorkspace, useOntologyVersion } from '@/modules/shared/components/LayoutContexts';

import { TypeManagementTab } from '../components/ObjectManagement/TypeManagementTab';

import { InstancesTab } from '../components/ObjectManagement/InstancesTab';

import { EntityDetailDrawer } from '../components/ObjectManagement/EntityDetailDrawer';

import type { ObjectType, ManagedEntity, ExtractionSource, AttributeValue } from '../components/ObjectManagement/types';

import {
  parsePropertiesToAttributes,
  toAttributeRecord,
  toAttributeRecordOrUndefined,
  toAttributeValue,
} from '../components/ObjectManagement/types';

import { PageTourWrapper, objectManagementTourSteps, PAGE_IDS } from '@/modules/guide';

import { useI18n } from '@/modules/shared/hooks/useI18n';

/** `getOntologyDocuments` 返回 `Record<string, unknown>`：文档字段一律按 unknown 收窄后再读 */
type OntologyDoc = Record<string, unknown>;

/** 归一化后的实体行：`queryEntities` / `getEntities` 两条来源先落到同一形状再渲染 */
interface NormalizedEntity {
  entity_id: string;
  name: string;
  type: string;
  properties: Record<string, AttributeValue>;
}

/** 文档里内嵌的实体（可选字段，缺省表示该文档没带这个字段） */
interface EmbeddedEntity {
  name_en?: string;
  confidence?: number;
  basic_properties?: Record<string, AttributeValue>;
  statistical_properties?: Record<string, AttributeValue>;
  capabilities?: Record<string, AttributeValue>;
  constraints?: AttributeValue[];
  /** 内嵌实体来自哪份文档 */
  _doc?: OntologyDoc;
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asNumber(value: unknown): number | undefined {
  return typeof value === 'number' ? value : undefined;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

/** 按路径读嵌套字符串：任一层缺失或类型不符都返回空串 */
function nestedString(source: Record<string, unknown> | undefined, ...path: string[]): string {
  let cursor: unknown = source;
  for (const key of path) {
    const record = asRecord(cursor);
    if (!record) return '';
    cursor = record[key];
  }
  return asString(cursor);
}

/** 按路径读嵌套数字：任一层缺失或类型不符都返回 undefined */
function nestedNumber(source: Record<string, unknown> | undefined, ...path: string[]): number | undefined {
  let cursor: unknown = source;
  for (const key of path) {
    const record = asRecord(cursor);
    if (!record) return undefined;
    cursor = record[key];
  }
  return asNumber(cursor);
}

/** 从属性记录里读字符串字段 */
function attrString(properties: Record<string, AttributeValue>, key: string): string {
  const value = properties[key];
  return typeof value === 'string' ? value : '';
}

/** 审计类实体不计入业务实体列表 */
const AUDIT_ENTITY_ID_PREFIXES = ['audit_', 'user_', 'resource_', 'service_'];

function isAuditEntity(entity: NormalizedEntity): boolean {
  if (entity.type.startsWith('Audit')) return true;
  return AUDIT_ENTITY_ID_PREFIXES.some((prefix) => entity.entity_id.startsWith(prefix));
}



export function ObjectManagement() {

  const { t } = useI18n();

  const { currentScenario } = useScenario();

  const { currentWorkspace } = useWorkspace();

  const { currentVersionId } = useOntologyVersion();

  const [activeTab, setActiveTab] = useState('types');

  const [objectTypes, setObjectTypes] = useState<ObjectType[]>([]);

  const [typesLoading, setTypesLoading] = useState(false);

  const [entities, setEntities] = useState<ManagedEntity[]>([]);

  const [loading, setLoading] = useState(false);

  const [searchText, setSearchText] = useState('');

  const [typeFilter, setTypeFilter] = useState<string>('all');

  const [sourceFilter, setSourceFilter] = useState<string>('all');

  const [detailOpen, setDetailOpen] = useState(false);

  const [viewingEntity, setViewingEntity] = useState<ManagedEntity | null>(null);

  const [extractionSources, setExtractionSources] = useState<ExtractionSource[]>([]);

  const [stats, setStats] = useState({

    total: 0, types: 0, structured: 0, unstructured: 0, computed: 0, inferred: 0,

    byCategory: {} as Record<string, number>,

  });



  const loadObjectTypes = async () => {

    setTypesLoading(true);

    try {

      const data = await api.listObjectTypes(false);

      setObjectTypes(Array.isArray(data) ? data : []);

    } catch {

      message.error(t('加载对象类型失败'));

    } finally {

      setTypesLoading(false);

    }

  };



  useEffect(() => {

        void (async () => {
      if (activeTab === 'types') loadObjectTypes();
    })();

  }, [activeTab]);



  const handleDeleteType = async (typeId: string) => {

    try {

      await api.deleteObjectType(typeId);

      message.success(t('删除成功'));

      loadObjectTypes();

    } catch {

      message.error(t('删除失败'));

    }

  };



  const handleSubmitType = async (values: unknown, editingType: ObjectType | null) => {

    if (editingType) {

      await api.updateObjectType(editingType.type_id, values);

      message.success(t('更新成功'));

    } else {

      await api.createObjectType(values);

      message.success(t('创建成功'));

    }

    loadObjectTypes();

  };



  



  const loadEntities = async () => {

    if (!currentScenario) return;

    setLoading(true);

    try {

      let rawEntities: NormalizedEntity[] = [];

      try {

        const result = await api.queryEntities({}, currentWorkspace || undefined);

        rawEntities = result.entities.map((e) => ({

          entity_id: e.entity_id, name: e.name, type: e.type,

          properties: toAttributeRecord(e.properties),

        }));

      } catch { /* 忽略：queryEntities 失败时走 getEntities 兜底 */ }



      if (rawEntities.length === 0) {

        try {

          // `getEntities` 的返回类型是 `shared/types.ts:Entity`
          // （`{ id, name, type, properties? }`，不是 `entity_id`/`entity_type`）
          const legacyEntities = await api.getEntities(currentScenario);

          rawEntities = legacyEntities.map((e) => ({

            entity_id: e.id, name: e.name, type: e.type,

            properties: toAttributeRecord(e.properties),

          }));

        } catch { /* 忽略：失败时保持当前状态 */ }

      }



      let ontologyDocs: OntologyDoc[] = [];

      try { ontologyDocs = await api.getOntologyDocuments(currentScenario, 50); } catch { /* 忽略：失败时保持当前状态 */ }



      const docMap = new Map<string, EmbeddedEntity>();

      ontologyDocs.forEach((doc) => {

        const docId = asString(doc.doc_id);

        if (docId) docMap.set(docId, { _doc: doc });

        const embeddedEntities = Array.isArray(doc.entities) ? doc.entities : [];

        for (const raw of embeddedEntities) {

          const record = asRecord(raw);

          const entityId = record ? asString(record.entity_id) : '';

          if (!record || !entityId) continue;

          docMap.set(entityId, {

            name_en: asString(record.name_en) || undefined,

            confidence: asNumber(record.confidence),

            basic_properties: toAttributeRecordOrUndefined(record.basic_properties),

            statistical_properties: toAttributeRecordOrUndefined(record.statistical_properties),

            capabilities: toAttributeRecordOrUndefined(record.capabilities),

            constraints: Array.isArray(record.constraints)

              ? record.constraints.map((item) => toAttributeValue(item))

              : undefined,

            _doc: doc,

          });

        }

      });



      const mapped: ManagedEntity[] = rawEntities

        .filter((entity) => !isAuditEntity(entity))

        .map((entity) => {

          const attrs = parsePropertiesToAttributes(entity.properties);

          const embedded = docMap.get(entity.entity_id);

          const doc = embedded?._doc;

          return {

            entity_id: entity.entity_id,

            name: entity.name,

            type: entity.type || 'Unknown',

            name_en: embedded?.name_en || undefined,

            attributes: attrs,

            // `queryEntities` 与 `getEntities` 都没声明 relation_count，保持 0
            relation_count: 0,

            created_at: nestedString(doc, 'source', 'collected_at') || new Date().toISOString(),

            updated_at: new Date().toISOString(),

            source_doc: asString(doc?.doc_id) || undefined,

            source_type: attrString(entity.properties, 'source_type') || nestedString(doc, 'source', 'type') || 'random',

            confidence: nestedNumber(doc, 'source', 'confidence') ?? embedded?.confidence,

            basic_properties: embedded?.basic_properties ?? toAttributeRecordOrUndefined(entity.properties.basic),

            statistical_properties: embedded?.statistical_properties ?? toAttributeRecordOrUndefined(entity.properties.statistical),

            capabilities: embedded?.capabilities ?? toAttributeRecordOrUndefined(entity.properties.capabilities),

            constraints: embedded?.constraints,

          };

        });



      setEntities(mapped);



      const typeSet = new Set(mapped.map(e => e.type));

      const categoryCount: Record<string, number> = {};

      let sc = 0, uc = 0, cc = 0, ic = 0;

      mapped.forEach(e => e.attributes.forEach(a => {

        categoryCount[a.semantic.category] = (categoryCount[a.semantic.category] || 0) + 1;

        if (a.source === 'structured') sc++;

        if (a.source === 'unstructured') uc++;

        if (a.source === 'computed') cc++;

        if (a.source === 'inferred') ic++;

      }));

      setStats({ total: mapped.length, types: typeSet.size, structured: sc, unstructured: uc, computed: cc, inferred: ic, byCategory: categoryCount });

    } catch {

      message.error(t('加载实体列表失败'));

    } finally {

      setLoading(false);

    }

  };

  



  const loadExtractionSources = async () => {

    if (!currentScenario) return;

    try {

      const docs = await api.getOntologyDocuments(currentScenario, 20);

      setExtractionSources(docs.map((doc): ExtractionSource => {

        const source = asRecord(doc.source);

        const meta = asRecord(doc.meta);

        return {

          doc_id: asString(doc.doc_id) || asString(doc.id),

          doc_type: asString(doc.doc_type) || 'unknown',

          source_type: asString(source?.type) || 'unknown',

          title: asString(meta?.title) || t('未命名'),

          description: asString(meta?.description),

          collected_at: asString(source?.collected_at),

          confidence: asNumber(source?.confidence) ?? 1.0,

          url: asString(source?.url) || undefined,

        };

      }));

    } catch { /* 忽略：失败时保持当前状态 */ }

  };

  useEffect(() => {

        void (async () => {
      if (currentScenario) {

        loadEntities();

        loadExtractionSources();

      }
    })();

  }, [currentScenario, currentVersionId]);



  const handleViewEntity = (entity: ManagedEntity) => {

    setViewingEntity(entity);

    setDetailOpen(true);

  };



  return (

    <PageTourWrapper pageId={PAGE_IDS.OBJECT_MANAGEMENT} steps={objectManagementTourSteps}>

    <div>

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={[

        {

          key: 'types',

          label: <span data-tour="obj-mgmt-type-tab">{t('对象类型定义')}</span>,

          children: (

            <TypeManagementTab

              objectTypes={objectTypes}

              loading={typesLoading}

              onCreateType={() => {}}

              onEditType={() => {}}

              onDeleteType={handleDeleteType}

              onSubmitType={handleSubmitType}

            />

          ),

        },

        {

          key: 'instances',

          label: <span data-tour="obj-mgmt-instances-tab">{t('实体实例')}</span>,

          children: (

            <InstancesTab

              entities={entities}

              loading={loading}

              stats={stats}

              extractionSources={extractionSources}

              currentScenario={currentScenario}

              searchText={searchText}

              onSearchTextChange={setSearchText}

              typeFilter={typeFilter}

              onTypeFilterChange={setTypeFilter}

              sourceFilter={sourceFilter}

              onSourceFilterChange={setSourceFilter}

              onViewEntity={handleViewEntity}

            />

          ),

        },

      ]} />



      <EntityDetailDrawer

        open={detailOpen}

        entity={viewingEntity}

        onClose={() => setDetailOpen(false)}

      />

    </div>

    </PageTourWrapper>

  );

}

