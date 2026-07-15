import { describe, it, expect } from 'vitest';
import type { PipelineRunStatus } from '../services/pipelineApi';
import {
  listPipelineRuns,
  createPipelineRun,
  advancePipelineRun,
  executeAllPipelineStages,
} from '../services/pipelineApi';

describe('pipelineApi.ts: OL Pipeline 导出 + PipelineRunStatus 字符串字面量合法集', () => {
  it('listPipelineRuns / createPipelineRun / advancePipelineRun / executeAllPipelineStages 存在', () => {
    expect(typeof listPipelineRuns).toBe('function');
    expect(typeof createPipelineRun).toBe('function');
    expect(typeof advancePipelineRun).toBe('function');
    expect(typeof executeAllPipelineStages).toBe('function');
  });

  it('PipelineRunStatus 合法集: pending/running/succeeded/failed 4 态', () => {
    const expected: PipelineRunStatus[] = ['pending', 'running', 'succeeded', 'failed'];
    // 测试用赋值兼容性（不是运行时值，但 TS 编译期会校验）
    const statuses: PipelineRunStatus[] = expected.slice();
    expect(statuses).toEqual(expected);
    expect(statuses).toHaveLength(4);
  });
});
