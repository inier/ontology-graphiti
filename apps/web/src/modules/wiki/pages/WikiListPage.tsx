/**
 * Wiki 列表页（/wiki）
 *
 * 覆盖四态：Loading（骨架）/ Empty / Error（展示 error_code + message）/ Populated
 * 筛选 status·owner·tag·keyword，表/卡双视图，服务层分页。
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Pagination } from 'antd';
import { Icon } from '@/modules/shared/components/Icon';
import { useWikiStore } from '../stores/wikiStore';
import { WIKI_API_MOCK } from '../services/wikiApi';
import { WikiFiltersBar, type WikiViewMode } from '../components/WikiFiltersBar';
import { WikiTable } from '../components/WikiTable';
import { WikiCardGrid } from '../components/WikiCardGrid';
import { WikiStateBlock } from '../components/WikiStateBlock';
import '../wiki.css';

export function WikiListPage() {
  const navigate = useNavigate();
  const {
    listPhase,
    entries,
    total,
    page,
    pageSize,
    filters,
    listError,
    fetchList,
    setFilters,
    setPage,
  } = useWikiStore();
  const [view, setView] = useState<WikiViewMode>('table');

  useEffect(() => {
    void fetchList();
  }, [fetchList, filters, page]);

  const openEntry = (entryId: string) => navigate(`/wiki/${entryId}`);
  const isEmpty = listPhase === 'ready' && entries.length === 0;

  return (
    <div className="wiki-page">
      <header>
        <h1 style={{ fontSize: 'var(--odap-font-size-3xl)', letterSpacing: 'var(--odap-tracking-tight)' }}>
          Wiki 条目
        </h1>
        <p style={{ color: 'var(--odap-color-fg-secondary)', marginTop: 'var(--odap-space-1)' }}>
          与本体内涵锚定的知识条目：每个条目必须绑定 owner，发布前校验内容哈希，合并只置 superseded 不物理删除。
        </p>
      </header>

      {WIKI_API_MOCK ? (
        <div className="wiki-banner" role="status">
          <Icon role="warning" size={16} />
          <span>
            演示数据（mock 开关开启 WIKI_API_MOCK=true）。F1 后端端点就绪后置 VITE_WIKI_MOCK=off 即切真实接口。
          </span>
        </div>
      ) : null}

      <WikiFiltersBar
        filters={filters}
        view={view}
        onChange={setFilters}
        onViewChange={setView}
        onRefresh={() => void fetchList()}
        disabled={listPhase === 'loading'}
      />

      <WikiStateBlock
        phase={listPhase}
        error={listError}
        isEmpty={isEmpty}
        emptyTitle="还没有符合条件的 Wiki 条目"
        emptyDesc="请放宽筛选条件（清空状态/owner/标签），或从仓库 docs/ 导入一批条目后再查看。"
        onRetry={() => void fetchList()}
      >
        {view === 'table' ? (
          <WikiTable entries={entries} onOpen={openEntry} />
        ) : (
          <WikiCardGrid entries={entries} onOpen={openEntry} />
        )}

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: 'var(--odap-space-4)',
          }}
        >
          <span className="wiki-meta">
            共 <span className="wiki-meta__num">{total}</span> 条 · 第{' '}
            <span className="wiki-meta__num">{page}</span> 页
          </span>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={total}
            showSizeChanger={false}
            onChange={(next) => setPage(next)}
            size="small"
          />
        </div>
      </WikiStateBlock>

      <div style={{ display: 'flex', gap: 'var(--odap-space-2)' }}>
        <Button icon={<Icon role="merge" size={20} />} onClick={() => navigate('/wiki/dedupe')}>
          去重合并
        </Button>
        <Button icon={<Icon role="document" size={16} />} onClick={() => navigate('/knowledge')}>
          知识库
        </Button>
      </div>
    </div>
  );
}
