/**
 * InlineChart 契约测试 —— 图表卡片内联渲染
 *
 * 后端契约：`impl/chart_renderer.py::ChartType` 声明 8 类
 *   line / bar / pie / scatter / heatmap / radar / map / network
 * `qa_engine._extract_charts` 实际只产出前 6 类中的 line/bar/pie/scatter/heatmap/radar。
 *
 * 本渲染器只实现 6 类。旧实现把另外两类也写进 `chartTypeNames` 并让 switch
 * 落到 `default` 分支 —— 于是 `map` / `network` 会被**静默画成折线图**：
 * 标题写着「地图」，画出来是折线。这属于伪实现，必须显式报不支持。
 *
 * 本测试钉住的行为：
 *  ① map / network 不调用 echarts.init（绝不画出一张错的图）；
 *  ② 不支持时给出具体原因，而不是笼统提示；
 *  ③ 6 类已实现类型仍然产出正确的 series.type。
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ChartSpec } from '../../types';
import { InlineChart } from '../InlineChart';

const { initMock, optionSink } = vi.hoisted(() => {
  const optionSink: unknown[] = [];
  const initMock = vi.fn(() => ({
    setOption: (opt: unknown) => {
      optionSink.push(opt);
    },
    resize: vi.fn(),
    dispose: vi.fn(),
  }));
  return { initMock, optionSink };
});

vi.mock('echarts', () => ({ init: initMock }));

vi.mock('@/modules/shared/hooks/useI18n', () => {
  // 真实插值：'该图表类型暂不支持内联渲染: {{type}}' + {type:'地图'} → '…: 地图'
  const t = (key: string, opts?: Record<string, unknown>) => {
    if (!opts) return key;
    return key.replace(/\{\{(\w+)\}\}/g, (_, k: string) => String(opts[k] ?? ''));
  };
  return { useI18n: () => ({ t }) };
});

type Series = { type?: string; data?: unknown };
type Option = { series?: Series[] };

function lastOption(): Option {
  return optionSink[optionSink.length - 1] as Option;
}

beforeEach(() => {
  initMock.mockClear();
  optionSink.length = 0;
});

describe('InlineChart —— 未实现类型必须显式报不支持', () => {
  it('map：不初始化 echarts，给出「需 GeoJSON 底图 + 合规约束」的具体原因', () => {
    const spec: ChartSpec = { chart_type: 'map', title: '门店分布', data: { points: [] } };
    render(<InlineChart spec={spec} />);

    expect(screen.getByTestId('inline-chart-unsupported')).toBeTruthy();
    expect(initMock).not.toHaveBeenCalled();
    // 标签仍在，用户能看到「地图」而不是一堆空白
    expect(screen.getByText('地图')).toBeTruthy();
    expect(screen.getByText(/该图表类型暂不支持内联渲染: 地图/)).toBeTruthy();
    expect(screen.getByText(/GeoJSON/)).toBeTruthy();
  });

  it('network：不初始化 echarts，指引去知识图谱画布', () => {
    const spec: ChartSpec = { chart_type: 'network', data: { nodes: [], links: [] } };
    render(<InlineChart spec={spec} />);

    expect(screen.getByTestId('inline-chart-unsupported')).toBeTruthy();
    expect(initMock).not.toHaveBeenCalled();
    expect(screen.getByText(/网络图请使用知识图谱画布查看/)).toBeTruthy();
  });

  it('不支持的分支绝不调用 setOption —— 否则就是画出错误的图', () => {
    render(<InlineChart spec={{ chart_type: 'map', data: {} }} />);
    expect(optionSink).toHaveLength(0);
  });
});

describe('InlineChart —— 已实现的 6 类产出正确的 series', () => {
  const cases: Array<{ type: ChartSpec['chart_type']; expected: string }> = [
    { type: 'line', expected: 'line' },
    { type: 'bar', expected: 'bar' },
    { type: 'pie', expected: 'pie' },
    { type: 'scatter', expected: 'scatter' },
    { type: 'radar', expected: 'radar' },
    { type: 'heatmap', expected: 'heatmap' },
  ];

  it.each(cases)('$type → series[0].type = $expected', ({ type, expected }) => {
    render(
      <InlineChart
        spec={{
          chart_type: type,
          title: '示例',
          data: {
            categories: ['甲', '乙'],
            values: [1, 2],
            points: [[1, 2]],
            xLabels: ['x1'],
            yLabels: ['y1'],
            heatmapData: [[0, 0, 5]],
          },
        }}
      />,
    );

    expect(screen.queryByTestId('inline-chart-unsupported')).toBeNull();
    expect(initMock).toHaveBeenCalledTimes(1);
    expect(lastOption().series?.[0]?.type).toBe(expected);
  });

  it('饼图用 categories + values 拼出 name/value 对', () => {
    render(<InlineChart spec={{ chart_type: 'pie', data: { categories: ['甲', '乙'], values: [7, 3] } }} />);
    const data = lastOption().series?.[0]?.data as Array<{ name: string; value: number }>;
    expect(data).toEqual([
      { name: '甲', value: 7 },
      { name: '乙', value: 3 },
    ]);
  });
});
