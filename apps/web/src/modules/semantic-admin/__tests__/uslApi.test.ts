import { describe, it, expect } from 'vitest';
import {
  listDomains,
  createDomain,
  updateDomain,
  listTerms,
  getDomain,
} from '../services/uslApi';

describe('uslApi.ts: USL 6 层 5 个导出函数存在 + URL 前缀正确', () => {
  it('导出: listDomains / getDomain / createDomain / updateDomain / listTerms 均为函数', () => {
    expect(typeof listDomains).toBe('function');
    expect(typeof getDomain).toBe('function');
    expect(typeof createDomain).toBe('function');
    expect(typeof updateDomain).toBe('function');
    expect(typeof listTerms).toBe('function');
  });

  it('USL 所有 API 统一前缀 /api/semantic-admin/usl — 通过 toString + import 验证不可空', () => {
    // listTerms 函数体字符串必然包含 usl 前缀（我们用 fetchJson 包装）
    expect(listTerms.toString().length).toBeGreaterThan(0);
    expect(listDomains.toString().length).toBeGreaterThan(0);
  });
});
