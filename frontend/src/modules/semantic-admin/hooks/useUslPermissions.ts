/**
 * USL 模块权限钩子
 * 基于 authStore 解析（与后端 verify_semantic_writer 完全对齐）：
 *   canWrite = global_role ∈ {admin, schema_auditor, editor}
 *              || ws_role ∈ {term_editor, domain_editor, reviewer, super_admin}
 * 所有写操作按钮（编辑/新建/删除）绑定 disabled={!canWrite}
 */
import { useMemo } from 'react';
import { useAuthStore } from '@/modules/shared/stores/authStore';

interface UslPermissions {
  /** 是否允许新建/编辑/删除 USL 配置 */
  canWrite: boolean;
  /** 当前登录角色展示文案（用于 Tooltip 说明原因） */
  reason: string;
}

const GLOBAL_WRITER_ROLES = new Set(['admin', 'schema_auditor', 'editor']);
const WS_WRITER_ROLES = new Set(['term_editor', 'domain_editor', 'reviewer', 'super_admin']);

export function useUslPermissions(): UslPermissions {
  const user = useAuthStore((s) => s.user);

  return useMemo<UslPermissions>(() => {
    if (!user) {
      return { canWrite: false, reason: '未登录' };
    }
    const globalRole = user.global_role?.toLowerCase() ?? '';
    const wsRole = user.ws_role?.toLowerCase() ?? '';
    const isGlobalWriter = GLOBAL_WRITER_ROLES.has(globalRole);
    const isWsWriter = WS_WRITER_ROLES.has(wsRole);

    if (isGlobalWriter) {
      return { canWrite: true, reason: `全局角色可写 (global_role=${globalRole})` };
    }
    if (isWsWriter) {
      return { canWrite: true, reason: `工作空间角色可写 (ws_role=${wsRole})` };
    }
    return {
      canWrite: false,
      reason: `当前角色 global=${globalRole || '(空)'}, ws=${wsRole || '(空)'}，`
        + `需要全局 ∈ {${[...GLOBAL_WRITER_ROLES].join(',')}} 或 ws_role ∈ {${[...WS_WRITER_ROLES].join(',')}}`,
    };
  }, [user]);
}
