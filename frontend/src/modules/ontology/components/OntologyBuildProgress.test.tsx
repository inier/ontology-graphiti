import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { OntologyBuildProgress } from './OntologyBuildProgress';
import type { Stage } from './OntologyBuildProgress';

const sampleStages: Stage[] = [
  { id: 'extract', name: '数据提取', status: 'completed' },
  { id: 'validate', name: '数据校验', status: 'in_progress' },
  { id: 'build', name: '图谱构建', status: 'pending' },
];

describe('OntologyBuildProgress', () => {
  it('renders without crashing with stages', () => {
    const { container } = render(
      <OntologyBuildProgress
        stages={sampleStages}
        currentStage="validate"
        progress={45}
      />
    );
    expect(container).toBeTruthy();
  });

  it('displays stage names and status tags', () => {
    render(
      <OntologyBuildProgress
        stages={sampleStages}
        currentStage="validate"
        progress={45}
      />
    );
    expect(screen.getByText('数据提取')).toBeTruthy();
    expect(screen.getByText('数据校验')).toBeTruthy();
    expect(screen.getByText('图谱构建')).toBeTruthy();
    expect(screen.getByText('已完成')).toBeTruthy();
    expect(screen.getByText('进行中')).toBeTruthy();
    expect(screen.getByText('等待中')).toBeTruthy();
  });

  it('displays progress bar', () => {
    render(
      <OntologyBuildProgress
        stages={sampleStages}
        currentStage="validate"
        progress={45}
      />
    );
    expect(screen.getByText('实时进度:')).toBeTruthy();
  });

  it('displays task description when provided', () => {
    render(
      <OntologyBuildProgress
        stages={sampleStages}
        currentStage="validate"
        progress={45}
        taskDescription="正在构建本体图谱"
      />
    );
    expect(screen.getByText('正在构建本体图谱')).toBeTruthy();
  });

  it('displays error message alert when provided', () => {
    render(
      <OntologyBuildProgress
        stages={sampleStages}
        currentStage="validate"
        progress={45}
        errorMessage="数据校验发现异常"
      />
    );
    expect(screen.getByText('数据校验发现异常')).toBeTruthy();
  });

  it('displays estimated time remaining', () => {
    render(
      <OntologyBuildProgress
        stages={sampleStages}
        currentStage="validate"
        progress={45}
        estimatedTimeRemaining={120}
      />
    );
    expect(screen.getByText('2分0秒')).toBeTruthy();
  });

  it('calls onStageClick when a stage is clicked', () => {
    const onStageClick = vi.fn();
    render(
      <OntologyBuildProgress
        stages={sampleStages}
        currentStage="validate"
        progress={45}
        onStageClick={onStageClick}
      />
    );
    fireEvent.click(screen.getByText('数据提取'));
    expect(onStageClick).toHaveBeenCalledTimes(1);
    expect(onStageClick).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'extract' })
    );
  });
});
