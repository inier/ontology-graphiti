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
  it('TOP_TAB_TO_PATH: 必须包含 7 个顶级 Tab（含 assets 与 approvals）', () => {
    const keys = Object.keys(TOP_TAB_TO_PATH) as Array<keyof typeof TOP_TAB_TO_PATH>;
    expect(keys).toEqual(
      expect.arrayContaining(['assets', 'usl', 'pipeline', 'candidates', 'quality', 'dashboard', 'approvals']),
    );
    expect(keys).toHaveLength(7);
  });

  it('PATH_TO_TOP_TAB: 主路径互为逆映射；别名路径（如 usl-ontologies）值必须为合法 tab', () => {
    // 主路径：TOP_TAB_TO_PATH 的每个 (tab, path) 在 PATH_TO_TOP_TAB 中反向映射回同一 tab
    for (const [tab, path] of Object.entries(TOP_TAB_TO_PATH)) {
      expect(PATH_TO_TOP_TAB[path]).toBe(tab);
    }
    // PATH_TO_TOP_TAB 是主映射的超集：允许把子路由别名（/semantic-admin/usl-ontologies
    // → 'usl'）指向所属 tab；每条记录的值都必须是 TOP_TAB_TO_PATH 的合法 tab key。
    const tabKeys = new Set(Object.keys(TOP_TAB_TO_PATH));
    for (const [path, tab] of Object.entries(PATH_TO_TOP_TAB)) {
      expect(tabKeys.has(tab as string)).toBe(true);
      expect(path.startsWith('/semantic-admin/')).toBe(true);
    }
    // 别名条目 = 总条目 − 主路径条目（当前 1 条：usl-ontologies → usl）
    expect(Object.keys(PATH_TO_TOP_TAB)).toHaveLength(8);
    expect(PATH_TO_TOP_TAB['/semantic-admin/usl-ontologies']).toBe('usl');
  });

  it('SEMANTIC_ADMIN_TAB_ITEMS_KEYS: 7 个 key，与 TOP_TAB_TO_PATH 对齐', () => {
    expect(SEMANTIC_ADMIN_TAB_ITEMS_KEYS).toHaveLength(7);
    expect(SEMANTIC_ADMIN_TAB_ITEMS_KEYS).toEqual(
      expect.arrayContaining([
        'assets', 'usl', 'pipeline', 'candidates', 'quality', 'dashboard', 'approvals',
      ]),
    );
  });

  it('getSemanticAdminTabItems(t): 7 个条目，keys 与 TOP_TAB_TO_PATH 对齐', () => {
    const items = getSemanticAdminTabItems(mockT);
    expect(items).toHaveLength(7);
    const actualKeys = items.map((it) => it!.key);
    expect(actualKeys).toEqual(
      expect.arrayContaining([
        'assets', 'usl', 'pipeline', 'candidates', 'quality', 'dashboard', 'approvals',
      ]),
    );
  });

  it('getSemanticAdminTabItems(t): label 走 i18n（调用 t 函数）', () => {
    const spyT = vi.fn((key: string) => key) as unknown as TFunction;
    const items = getSemanticAdminTabItems(spyT);
    // 7 个 Tab label 均应调用 t
    expect(spyT).toHaveBeenCalledTimes(7);
    // 至少调用了 '语义资产 Pipeline'、'USL 规范配置' 和 '审批工作台'
    expect(spyT).toHaveBeenCalledWith('语义资产 Pipeline');
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
