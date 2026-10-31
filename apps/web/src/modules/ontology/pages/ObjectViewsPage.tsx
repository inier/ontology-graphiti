/**
 * ObjectViewsPage —— 对象视图工作区页面（FR-036）。
 *
 * 组合关系（页面只做编排，不重复实现能力）：
 *   - `ObjectViewPage`：视图列表 / 查询 / 导出 / 权限（消费 /api/ontology/views）
 *   - `ViewDesigner`：字段 / 过滤 / 排序 / 行数上限 / 权限说明（同上，PATCH 语义的 PUT）
 *
 * 设计器用全屏宽 Modal 承载：它是三栏（对象类型树 6 + 配置 12 + 预览 6）布局，
 * 塞进窄抽屉会把三栏压成一栏，信息密度反而低于列表页。
 */
import { useCallback, useState } from 'react';
import { Modal } from 'antd';
import ObjectViewPage from './ObjectViewPage';
import ViewDesigner from '../components/ViewDesigner';
import { useWorkspace } from '@/modules/shared/components/LayoutContexts';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export function ObjectViewsPage() {
  const { t } = useI18n('ontology');
  const { currentWorkspace } = useWorkspace();
  const [designerOpen, setDesignerOpen] = useState(false);
  /** undefined = 新建；有值 = 编辑该视图 */
  const [editingViewId, setEditingViewId] = useState<string | undefined>(undefined);
  /** 保存后强制重挂载列表页，触发重新拉取（列表页自己没有暴露 refresh 句柄） */
  const [reloadToken, setReloadToken] = useState(0);

  const openDesigner = useCallback((viewId?: string) => {
    setEditingViewId(viewId);
    setDesignerOpen(true);
  }, []);

  const handleSaved = useCallback(() => {
    setDesignerOpen(false);
    setReloadToken((n) => n + 1);
  }, []);

  return (
    <>
      <ObjectViewPage
        key={reloadToken}
        workspaceId={currentWorkspace}
        onCreateView={() => openDesigner(undefined)}
        onDesignView={(viewId) => openDesigner(viewId)}
      />
      <Modal
        open={designerOpen}
        onCancel={() => setDesignerOpen(false)}
        footer={null}
        width={1280}
        destroyOnHidden
        title={editingViewId ? t('编辑视图') : t('新建视图')}
      >
        <ViewDesigner
          viewId={editingViewId}
          onSaved={handleSaved}
          onClose={() => setDesignerOpen(false)}
        />
      </Modal>
    </>
  );
}

export default ObjectViewsPage;
