import { describe, it, expect } from 'vitest';
import {
  TOP_TAB_TO_PATH,
  PATH_TO_TOP_TAB,
  SEMANTIC_ADMIN_TAB_ITEMS,
} from '../constants';

/**
 * 常量单元测试：
 *  - 6 个顶层 Tab 都有映射（包含 approvals）
 *  - TOP_TAB_TO_PATH ⇄ PATH_TO_TOP_TAB 双射（互为逆映射）
 *  - SEMANTIC_ADMIN_TAB_ITEMS 有 6 条（包含 approvals）
 */

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

  it('SEMANTIC_ADMIN_TAB_ITEMS: 6 个条目，keys 与 TOP_TAB_TO_PATH 对齐', () => {
    expect(SEMANTIC_ADMIN_TAB_ITEMS).toHaveLength(6);
    const actualKeys = SEMANTIC_ADMIN_TAB_ITEMS.map((it) => it!.key);
    expect(actualKeys).toEqual(
      expect.arrayContaining([
        'usl', 'pipeline', 'candidates', 'quality', 'dashboard', 'approvals',
      ]),
    );
  });

  it('Approvals 路由存在并指向 approvals tab（验收清单 FE-01 前置条件）', () => {
    expect(TOP_TAB_TO_PATH.approvals).toBe('/semantic-admin/approvals');
    expect(PATH_TO_TOP_TAB['/semantic-admin/approvals']).toBe('approvals');
    const approvalsItem = SEMANTIC_ADMIN_TAB_ITEMS.find((it) => it!.key === 'approvals');
    expect(approvalsItem).toBeDefined();
  });
});
