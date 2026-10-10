/**
 * 提取模式（EntityExtractor mode）API 客户端（ADR-089 子项目 C）。
 *
 * 后端契约：
 *   GET  /api/semantic-admin/extractor-mode   读取（显式配置 + 生效 mode + 可选集 + 描述）
 *   PUT  /api/semantic-admin/extractor-mode   切换（admin）{ mode, updated_by? }
 */
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const URL = `${API_BASE}/api/semantic-admin/extractor-mode`;

export type ExtractorMode = 'off' | 'inject' | 'query';

export interface ExtractorModeInfo {
  status: string;
  /** 显式配置值；未配置为 null */
  mode: ExtractorMode | null;
  /** 生效 mode（配置 > env > 默认） */
  effective_mode: ExtractorMode;
  default_mode: ExtractorMode;
  available_modes: ExtractorMode[];
  descriptions: Record<ExtractorMode, string>;
  updated_by?: string | null;
  updated_at?: string | null;
}

/** 读取当前提取模式配置 */
export async function getExtractorMode(): Promise<ExtractorModeInfo> {
  return fetchJson<ExtractorModeInfo>(URL);
}

/** 切换提取模式（需 admin） */
export async function setExtractorMode(
  mode: ExtractorMode,
  updatedBy?: string,
): Promise<ExtractorModeInfo> {
  return fetchJson<ExtractorModeInfo>(URL, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, updated_by: updatedBy }),
  });
}

/** 聚合导出（与 gapApi 等模块风格一致） */
export const extractorModeApi = { getExtractorMode, setExtractorMode };
