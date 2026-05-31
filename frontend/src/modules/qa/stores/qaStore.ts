import { create } from 'zustand';
import { askTemporalQuestion, renderChart, type TemporalAskRequest, type ChartRequest } from '../services/qaApi';

interface TemporalResult {
  question: string;
  answer: string;
  valid_time?: string;
  time_type?: string;
  entity_count: number;
}

interface ChartResult {
  chart_type: string;
  render_mode: string;
  title: string;
  spec: Record<string, unknown>;
}

interface QAState {
  temporalLoading: boolean;
  temporalResult: TemporalResult | null;
  temporalError: string | null;

  chartLoading: boolean;
  chartResult: ChartResult | null;
  chartError: string | null;

  askTemporal: (request: TemporalAskRequest) => Promise<void>;
  renderChart: (request: ChartRequest) => Promise<void>;
  clearTemporal: () => void;
  clearChart: () => void;
}

export const useQAStore = create<QAState>((set) => ({
  temporalLoading: false,
  temporalResult: null,
  temporalError: null,

  chartLoading: false,
  chartResult: null,
  chartError: null,

  askTemporal: async (request: TemporalAskRequest) => {
    set({ temporalLoading: true, temporalError: null });
    try {
      const result = await askTemporalQuestion(request);
      set({ temporalResult: result, temporalLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : '时序问答失败';
      set({ temporalError: message, temporalLoading: false });
    }
  },

  renderChart: async (request: ChartRequest) => {
    set({ chartLoading: true, chartError: null });
    try {
      const result = await renderChart(request);
      set({ chartResult: result, chartLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : '图表渲染失败';
      set({ chartError: message, chartLoading: false });
    }
  },

  clearTemporal: () => set({ temporalResult: null, temporalError: null }),
  clearChart: () => set({ chartResult: null, chartError: null }),
}));
