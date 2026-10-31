/**
 * 条目状态元数据（SPEC §6 wiki_entries.status）
 *
 * 与组件分离：常量文件不导出组件，避免 react-refresh/only-export-components 失效。
 * 颜色全部来自语义 Token，不使用彩色侧条纹（UIUX §7.3 绝对禁令 #1）。
 */
import type { WikiEntryStatus } from '../services/wikiTypes';

export interface StatusTone {
  label: string;
  bg: string;
  fg: string;
  border: string;
}

export const STATUS_TONES: Record<WikiEntryStatus, StatusTone> = {
  draft: {
    label: '草稿',
    bg: 'var(--odap-color-bg-subtle)',
    fg: 'var(--odap-color-fg-secondary)',
    border: 'var(--odap-color-border-strong)',
  },
  review: {
    label: '评审中',
    bg: 'var(--odap-color-warn-bg)',
    fg: 'var(--odap-color-warn)',
    border: 'var(--odap-color-warn)',
  },
  published: {
    label: '已发布',
    bg: 'var(--odap-color-success-bg)',
    fg: 'var(--odap-color-success)',
    border: 'var(--odap-color-success)',
  },
  superseded: {
    label: '已被取代',
    bg: 'var(--odap-color-info-bg)',
    fg: 'var(--odap-color-info)',
    border: 'var(--odap-color-info)',
  },
  archived: {
    label: '已归档',
    bg: 'var(--odap-color-bg-subtle)',
    fg: 'var(--odap-color-fg-muted)',
    border: 'var(--odap-color-border)',
  },
};

export const WIKI_STATUS_OPTIONS: Array<{ value: WikiEntryStatus | 'all'; label: string }> = [
  { value: 'all', label: '全部状态' },
  { value: 'draft', label: STATUS_TONES.draft.label },
  { value: 'review', label: STATUS_TONES.review.label },
  { value: 'published', label: STATUS_TONES.published.label },
  { value: 'superseded', label: STATUS_TONES.superseded.label },
  { value: 'archived', label: STATUS_TONES.archived.label },
];
