import { describe, it, expect, vi } from 'vitest';
import {
  TOP_TAB_TO_PATH,
  PATH_TO_TOP_TAB,
  getSemanticAdminTabItems,
  SEMANTIC_ADMIN_TAB_ITEMS_KEYS,
} from '../constants';
import type { TFunction } from 'i18next';

/**
 * 常量单元测试：
 *  - 6 个顶层 Tab 都有映射（包含 approvals）
 *  - TOP_TAB_TO_PATH ⇄ PATH_TO_TOP_TAB 双射（互为逆映射）
 *  - getSemanticAdminTabItems(t) 返回 6 条（包含 approvals）
 *
 * 注意：SEMANTIC_ADMIN_TAB_ITEMS 已重构为函数 getSemanticAdminTabItems(t)，
 * 以便 Tab label 走 i18n。测试使用 mock t（identity，模拟 zh-CN 行为）。
 */

// mock t：identity 函数（zh-CN 下 t('中文') === '中文'）
const mockT = ((key: string) => key) as unknown as TFunction;

describe('constants: semantic-admin 顶层 Tab & 路径映射', () => {
  it('TOP_TAB_TO_PATH: 必须包含 6 个顶级 Tab（含 approvals）', () => {
    const keys = Object.keys(TOP_TAB_TO_PATH) as Array<keyof typeof TOP_TAB_TO_PATH>;
    expect(keys).toEqual(
      expect.arrayContaining(['usl', 'pipeline', 'candidates', 'quality', 'dashboard', 'approvals']),
    );
    expect(keys).toHaveLength(6);
  });

  it('PATH_TO_TOP_TAB: 必须与 TOP_TAB_TO_PATH 互为逆映射', () => {
    for (const [tab, path] of Object.entries(TOP_TAB_TO_PATH)) {
      expect(PATH_TO_TOP_TAB[path]).toBe(tab);
    }
    expect(Object.keys(PATH_TO_TOP_TAB)).toHaveLength(6);
  });

  it('SEMANTIC_ADMIN_TAB_ITEMS_KEYS: 6 个 key，与 TOP_TAB_TO_PATH 对齐', () => {
    expect(SEMANTIC_ADMIN_TAB_ITEMS_KEYS).toHaveLength(6);
    expect(SEMANTIC_ADMIN_TAB_ITEMS_KEYS).toEqual(
      expect.arrayContaining([
        'usl', 'pipeline', 'candidates', 'quality', 'dashboard', 'approvals',
      ]),
    );
  });

  it('getSemanticAdminTabItems(t): 6 个条目，keys 与 TOP_TAB_TO_PATH 对齐', () => {
    const items = getSemanticAdminTabItems(mockT);
    expect(items).toHaveLength(6);
    const actualKeys = items.map((it) => it!.key);
    expect(actualKeys).toEqual(
      expect.arrayContaining([
        'usl', 'pipeline', 'candidates', 'quality', 'dashboard', 'approvals',
      ]),
    );
  });

  it('getSemanticAdminTabItems(t): label 走 i18n（调用 t 函数）', () => {
    const spyT = vi.fn((key: string) => key) as unknown as TFunction;
    const items = getSemanticAdminTabItems(spyT);
    // 6 个 Tab label 均应调用 t
    expect(spyT).toHaveBeenCalledTimes(6);
    // 至少调用了 'USL 规范配置' 和 '审批工作台'
    expect(spyT).toHaveBeenCalledWith('USL 规范配置');
    expect(spyT).toHaveBeenCalledWith('审批工作台');
    // items 不为空
    expect(items.every((it) => it!.label != null)).toBe(true);
  });

  it('Approvals 路由存在并指向 approvals tab（验收清单 FE-01 前置条件）', () => {
    expect(TOP_TAB_TO_PATH.approvals).toBe('/semantic-admin/approvals');
    expect(PATH_TO_TOP_TAB['/semantic-admin/approvals']).toBe('approvals');
    const items = getSemanticAdminTabItems(mockT);
    const approvalsItem = items.find((it) => it!.key === 'approvals');
    expect(approvalsItem).toBeDefined();
  });
});
