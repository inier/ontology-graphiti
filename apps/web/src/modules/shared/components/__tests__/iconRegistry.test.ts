/**
 * 图标注册表契约测试（ADR-092）
 *
 * 断言「语义角色 → 图标 + 最小尺寸」这张表本身的合法性：
 * 角色唯一、minSize 合法、复杂字形不低于 20px、跨工作区角色齐备。
 */
import { describe, expect, it } from 'vitest';
import { ICON_ROLES, ICON_ROLE_NAMES } from '../iconRegistry';

describe('iconRegistry', () => {
  it('每个角色都绑定真实图标组件与 PascalCase 图标名', () => {
    for (const [role, spec] of Object.entries(ICON_ROLES)) {
      expect(spec.icon, `${role} 未绑定图标组件`).toBeTruthy();
      expect(spec.iconName, `${role} 的 iconName 缺失`).toMatch(/^[A-Z][A-Za-z0-9]*$/);
    }
  });

  it('minSize 只能是 16 / 20 / 24 三档之一', () => {
    const allowed = [16, 20, 24];
    for (const [role, spec] of Object.entries(ICON_ROLES)) {
      expect(allowed, `${role} 的 minSize=${spec.minSize} 不在三档内`).toContain(spec.minSize);
    }
  });

  it('复杂字形（多内轮廓）最小尺寸必须是 20px', () => {
    const complexRoles = [
      'dashboard',
      'ontology',
      'governance',
      'settings',
      'blueprint',
      'modeling',
      'asset',
      'tbox',
      'scan',
      'drift',
      'chart',
      'runtime',
      'tree',
      'merge',
      'diff',
    ].filter((role) => role in ICON_ROLES);

    expect(complexRoles.length).toBeGreaterThanOrEqual(12);
    for (const role of complexRoles) {
      expect(ICON_ROLES[role as keyof typeof ICON_ROLES].minSize, `${role} 允许被缩到 16px`).toBe(20);
    }
  });

  it('6 个工作区角色全部登记（AC-19）', () => {
    const workspaceRoles = ['dashboard', 'ontology', 'knowledge', 'ask', 'governance', 'settings'];
    for (const role of workspaceRoles) {
      expect(ICON_ROLE_NAMES, `${role} 未登记`).toContain(role);
    }
  });

  it('16 组 ODAP 语义概念角色齐备（UIUX §5.2 B 组核心项）', () => {
    const conceptRoles = [
      'gap',
      'asset',
      'routingTicket',
      'usl',
      'metricType',
      'provenance',
      'history',
      'decision',
      'simulation',
      'drift',
      'scan',
      'changeProposal',
      'shaclShape',
      'ontologyVersion',
      'tbox',
      'abox',
      'qualityGate',
      'gapLoop',
    ];
    for (const role of conceptRoles) {
      expect(ICON_ROLE_NAMES, `${role} 未登记`).toContain(role);
    }
  });

  it('角色名是稳定的 camelCase 语义键，不是图标名', () => {
    for (const role of ICON_ROLE_NAMES) {
      expect(role, `${role} 看起来像图标名而非语义角色`).toMatch(/^[a-z][A-Za-z]*$/);
      expect(role).not.toMatch(/^[A-Z]/);
    }
  });
});
