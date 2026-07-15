/**
 * T068 useTypeInference — 属性名 → 类型推断 hook
 *
 * 功能：
 * - debounce 300ms 后调用 /api/ontology-assistant/infer-type
 * - 返回推断类型 + 约束建议
 * - 支持手动触发约束建议（基于已选数据类型）
 *
 * 使用场景：
 * - AIInlineCompletion 组件：用户输入属性名时实时推断类型
 * - PropertyEditor：属性名变化时显示类型建议
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { ontologyApi } from '../services/ontologyApi';

export interface TypeInferenceResult {
  /** 推断的数据类型（STRING/INTEGER/FLOAT/BOOLEAN/DATETIME/JSON 等） */
  inferredType: string;
  /** 匹配规则（exact/prefix/suffix/contains/default） */
  matchRule: string;
  /** 置信度 0-1 */
  confidence: number;
  /** 附带的约束建议（如有） */
  constraints?: Record<string, unknown>;
}

export interface ConstraintSuggestion {
  name: string;
  rule: string;
  description?: string;
}

export interface UseTypeInferenceResult {
  /** 当前推断结果（null 表示无输入或加载中） */
  inference: TypeInferenceResult | null;
  /** 加载状态 */
  loading: boolean;
  /** 错误信息 */
  error: string | null;
  /** 约束建议列表（基于已选数据类型） */
  constraintSuggestions: ConstraintSuggestion[];
  /** 约束建议加载状态 */
  constraintsLoading: boolean;
  /** 手动触发类型推断 */
  inferType: (propertyName: string) => void;
  /** 手动触发约束建议（需要属性名 + 数据类型） */
  suggestConstraints: (propertyName: string, dataType: string) => Promise<void>;
  /** 清空状态 */
  reset: () => void;
}

const DEBOUNCE_MS = 300;

export function useTypeInference(): UseTypeInferenceResult {
  const [inference, setInference] = useState<TypeInferenceResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [constraintSuggestions, setConstraintSuggestions] = useState<ConstraintSuggestion[]>([]);
  const [constraintsLoading, setConstraintsLoading] = useState(false);

  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // 内部：执行类型推断请求
  const doInfer = useCallback(async (propertyName: string) => {
    if (!propertyName || propertyName.trim().length < 2) {
      setInference(null);
      setLoading(false);
      return;
    }

    // 取消上一个请求
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const result = await ontologyApi.aiAssistant.inferType(propertyName.trim());
      if (controller.signal.aborted) return;

      setInference({
        inferredType: result.inferred_type,
        matchRule: result.match_rule,
        confidence: result.confidence,
        constraints: result.constraints,
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      // 静默失败：AI 推断不可用不应阻断手动编辑
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setInference(null);
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, []);

  // 公开：debounce 300ms 后触发推断
  const inferType = useCallback(
    (propertyName: string) => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      debounceTimerRef.current = setTimeout(() => {
        void doInfer(propertyName);
      }, DEBOUNCE_MS);
    },
    [doInfer],
  );

  // 公开：约束建议（无 debounce，按需触发）
  const suggestConstraints = useCallback(
    async (propertyName: string, dataType: string) => {
      if (!propertyName || !dataType) {
        setConstraintSuggestions([]);
        return;
      }

      setConstraintsLoading(true);
      try {
        const result = await ontologyApi.aiAssistant.suggestConstraints(propertyName, dataType);
        setConstraintSuggestions(result.constraints || []);
      } catch (err) {
        // 静默失败
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        setConstraintSuggestions([]);
      } finally {
        setConstraintsLoading(false);
      }
    },
    [],
  );

  const reset = useCallback(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }
    abortControllerRef.current?.abort();
    setInference(null);
    setError(null);
    setLoading(false);
    setConstraintSuggestions([]);
    setConstraintsLoading(false);
  }, []);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      abortControllerRef.current?.abort();
    };
  }, []);

  return {
    inference,
    loading,
    error,
    constraintSuggestions,
    constraintsLoading,
    inferType,
    suggestConstraints,
    reset,
  };
}
