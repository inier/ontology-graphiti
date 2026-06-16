import { useState, useEffect } from 'react';
import { Tabs, message } from 'antd';
import { api } from '@/modules/shared/services/api';
import { useScenario, useWorkspace, useOntologyVersion } from '@/modules/shared/components/AppLayout';
import { TypeManagementTab } from '../components/ObjectManagement/TypeManagementTab';
import { InstancesTab } from '../components/ObjectManagement/InstancesTab';
import { EntityDetailDrawer } from '../components/ObjectManagement/EntityDetailDrawer';
import type { ObjectType, ManagedEntity, ExtractionSource } from '../components/ObjectManagement/types';
import { parsePropertiesToAttributes, getAttributeSemantic, detectValueType } from '../components/ObjectManagement/types';
import { PageTourWrapper, objectManagementTourSteps, PAGE_IDS } from '@/modules/guide';

export function ObjectManagement() {
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
      message.error('加载对象类型失败');
    } finally {
      setTypesLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'types') loadObjectTypes();
  }, [activeTab]);

  const handleDeleteType = async (typeId: string) => {
    try {
      await api.deleteObjectType(typeId);
      message.success('删除成功');
      loadObjectTypes();
    } catch {
      message.error('删除失败');
    }
  };

  const handleSubmitType = async (values: any, editingType: ObjectType | null) => {
    if (editingType) {
      await api.updateObjectType(editingType.type_id, values);
      message.success('更新成功');
    } else {
      await api.createObjectType(values);
      message.success('创建成功');
    }
    loadObjectTypes();
  };

  useEffect(() => {
    if (currentScenario) {
      loadEntities();
      loadExtractionSources();
    }
  }, [currentScenario, currentVersionId]);

  const loadEntities = async () => {
    if (!currentScenario) return;
    setLoading(true);
    try {
      let result: any = null;
      try { result = await api.queryEntities({}, currentWorkspace || undefined); } catch {}

      let rawEntities: any[] = [];
      if (result?.entities?.length > 0) {
        rawEntities = result.entities;
      } else {
        try {
          const oldResult = await api.getEntities(currentScenario);
          rawEntities = oldResult.map((e: any) => ({
            entity_id: e.id || e.entity_id, name: e.name, type: e.type || e.entity_type,
            properties: e.properties || { basic: e.basic_properties, statistical: e.statistical_properties, capabilities: e.capabilities },
          }));
        } catch {}
      }

      let ontologyDocs: any[] = [];
      try { ontologyDocs = await api.getOntologyDocuments(currentScenario, 50); } catch {}

      const docMap = new Map<string, any>();
      ontologyDocs.forEach((doc: any) => {
        if (doc.doc_id) docMap.set(doc.doc_id, doc);
        if (doc.entities) doc.entities.forEach((e: any) => { if (e.entity_id) docMap.set(e.entity_id, { ...e, _doc: doc }); });
      });

      const mapped: ManagedEntity[] = rawEntities
        .filter((e: any) => {
          const et = e.type || e.entity_type;
          const eid = e.entity_id || e.id;
          return !(et?.startsWith('Audit') || eid?.startsWith('audit_') || eid?.startsWith('user_') || eid?.startsWith('resource_') || eid?.startsWith('service_'));
        })
        .map((e: any) => {
          const attrs = parsePropertiesToAttributes(e.properties || {});
          const originalEntity = docMap.get(e.entity_id);
          const doc = originalEntity?._doc;
          return {
            entity_id: e.entity_id || e.id, name: e.name, type: e.type || e.entity_type || 'Unknown',
            name_en: originalEntity?.name_en || e.name_en, attributes: attrs, relation_count: e.relation_count || 0,
            created_at: doc?.source?.collected_at || new Date().toISOString(), updated_at: new Date().toISOString(),
            source_doc: doc?.doc_id, source_type: e.properties?.source_type || doc?.source?.type || 'random',
            confidence: doc?.source?.confidence || originalEntity?.confidence,
            basic_properties: originalEntity?.basic_properties || e.properties?.basic,
            statistical_properties: originalEntity?.statistical_properties || e.properties?.statistical,
            capabilities: originalEntity?.capabilities || e.properties?.capabilities,
            constraints: originalEntity?.constraints,
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
      message.error('加载实体列表失败');
    } finally {
      setLoading(false);
    }
  };

  const loadExtractionSources = async () => {
    if (!currentScenario) return;
    try {
      const docs = await api.getOntologyDocuments(currentScenario, 20);
      setExtractionSources(docs.map((doc: any) => ({
        doc_id: doc.doc_id || doc.id, doc_type: doc.doc_type || 'unknown',
        source_type: doc.source?.type || 'unknown', title: doc.meta?.title || '未命名',
        description: doc.meta?.description || '', collected_at: doc.source?.collected_at || '',
        confidence: doc.source?.confidence || 1.0, url: doc.source?.url,
      })));
    } catch {}
  };

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
          label: <span data-tour="obj-mgmt-type-tab">对象类型定义</span>,
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
          label: <span data-tour="obj-mgmt-instances-tab">实体实例</span>,
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
