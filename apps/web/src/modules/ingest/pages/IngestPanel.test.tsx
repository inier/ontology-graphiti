import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { IngestPanel, getLogError } from './IngestPanel';

// ─── Mocks ───

vi.mock('@/modules/shared', () => ({
  useScenario: () => ({ currentScenario: 'scenario-1' }),
  useWorkspace: () => ({ currentWorkspace: 'ws-1' }),
  api: {
    getIngestHistory: vi.fn().mockResolvedValue([]),
    getRandomGeneratorTypes: vi.fn().mockResolvedValue({
      types: [{ type: 'military', name: '军事事件', description: '生成军事对抗事件' }],
    }),
    ingest: vi.fn(),
    ingestFile: vi.fn(),
    buildOntology: vi.fn(),
    getFullIngestRecord: vi.fn(),
    switchScenarioOntologyVersion: vi.fn(),
  },
  fetchJson: vi.fn(),
  API_BASE: 'http://localhost:8000',
  // 轻量桩：按列 render 展开数据行，便于断言行内按钮
  AdvancedTable: ({ dataSource, columns }: { dataSource: any[]; columns: any[] }) => (
    <table>
      <tbody>
        {dataSource.map((record, rowIndex) => (
          <tr key={record.id}>
            {columns.map((col, colIndex) => (
              <td key={colIndex}>
                {col.render
                  ? col.render(record[col.dataIndex], record, rowIndex)
                  : record[col.dataIndex]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  ),
}));

vi.mock('../hooks', () => ({
  useBuildProgress: () => ({ stage: '', progress: 0, message: '', isConnected: false }),
}));

vi.mock('../components/WebSearchPanel', () => ({
  default: () => <div data-testid="web-search-panel">WebSearchPanel</div>,
}));

vi.mock('../components/WebCrawlPanel', () => ({
  default: () => <div data-testid="web-crawl-panel">WebCrawlPanel</div>,
}));

vi.mock('@/modules/guide', () => ({
  PageTourWrapper: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  ingestTourSteps: [],
  PAGE_IDS: { INGEST: 'ingest' },
}));

// ─── Tests ───

describe('IngestPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the ingest panel with tabs', async () => {
    render(<IngestPanel />);

    await waitFor(() => {
      expect(screen.getByText('文本摄入')).toBeTruthy();
      expect(screen.getByText('新闻摄入')).toBeTruthy();
      expect(screen.getByText('JSON数据')).toBeTruthy();
      expect(screen.getByText('自然语言')).toBeTruthy();
      expect(screen.getByText('随机事件')).toBeTruthy();
      expect(screen.getByText('手动录入')).toBeTruthy();
      expect(screen.getByText('文件上传')).toBeTruthy();
      expect(screen.getByText('联网搜索')).toBeTruthy();
      expect(screen.getByText('智能爬取')).toBeTruthy();
    });
  });

  it('renders the history section with refresh button', async () => {
    render(<IngestPanel />);

    await waitFor(() => {
      expect(screen.getByText('刷新')).toBeTruthy();
    });
  });

  it('shows empty state when no ingest history', async () => {
    render(<IngestPanel />);

    await waitFor(() => {
      expect(screen.getByText('暂无摄入记录，请通过上方方式摄入数据')).toBeTruthy();
    });
  });

  it('switches tabs when clicking a different tab', async () => {
    render(<IngestPanel />);

    // Wait for initial render
    await waitFor(() => {
      expect(screen.getByText('文本摄入')).toBeTruthy();
    });

    // Click on "新闻摄入" tab
    const newsTab = screen.getByText('新闻摄入');
    fireEvent.click(newsTab);

    // The news tab should show the URL input
    await waitFor(() => {
      expect(screen.getByPlaceholderText('请输入新闻URL')).toBeTruthy();
    });
  });

  it('switches to JSON data tab and shows textarea', async () => {
    render(<IngestPanel />);

    await waitFor(() => {
      expect(screen.getByText('JSON数据')).toBeTruthy();
    });

    const jsonTab = screen.getByText('JSON数据');
    fireEvent.click(jsonTab);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('请输入JSON格式的本体数据')).toBeTruthy();
    });
  });

  it('switches to natural language tab', async () => {
    render(<IngestPanel />);

    await waitFor(() => {
      expect(screen.getByText('自然语言')).toBeTruthy();
    });

    const nlTab = screen.getByText('自然语言');
    fireEvent.click(nlTab);

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/用自然语言描述一个事件/)).toBeTruthy();
    });
  });

  it('switches to file upload tab', async () => {
    render(<IngestPanel />);

    await waitFor(() => {
      expect(screen.getByText('文件上传')).toBeTruthy();
    });

    const fileTab = screen.getByText('文件上传');
    fireEvent.click(fileTab);

    await waitFor(() => {
      expect(screen.getByText('点击或拖拽文件到此区域上传')).toBeTruthy();
    });
  });

  it('renders WebSearchPanel on web search tab', async () => {
    render(<IngestPanel />);

    await waitFor(() => {
      expect(screen.getByText('联网搜索')).toBeTruthy();
    });

    const webSearchTab = screen.getByText('联网搜索');
    fireEvent.click(webSearchTab);

    await waitFor(() => {
      expect(screen.getByTestId('web-search-panel')).toBeTruthy();
    });
  });

  it('renders WebCrawlPanel on web crawl tab', async () => {
    render(<IngestPanel />);

    await waitFor(() => {
      expect(screen.getByText('智能爬取')).toBeTruthy();
    });

    const webCrawlTab = screen.getByText('智能爬取');
    fireEvent.click(webCrawlTab);

    await waitFor(() => {
      expect(screen.getByTestId('web-crawl-panel')).toBeTruthy();
    });
  });

  it('shows random event generator with type selector', async () => {
    render(<IngestPanel />);

    await waitFor(() => {
      expect(screen.getByText('随机事件')).toBeTruthy();
    });

    const randomTab = screen.getByText('随机事件');
    fireEvent.click(randomTab);

    await waitFor(() => {
      expect(screen.getByText('生成随机事件')).toBeTruthy();
      expect(screen.getByText('事件类型：')).toBeTruthy();
    });
  });

  it('shows the concrete failure reason when a stage failed', async () => {
    const shared = await import('@/modules/shared');
    const apiMock = shared.api as unknown as Record<string, ReturnType<typeof vi.fn>>;

    apiMock.getIngestHistory.mockResolvedValue([
      {
        id: 'ing-1',
        source: 'manual',
        status: 'failed',
        record_count: 1,
        processed_count: 0,
        failed_count: 1,
        start_time: '2026-09-24T10:00:00.000Z',
        build_status: 'failed',
        builds: [],
      },
    ]);

    // 后端两个来源都可能带原因：error_message 与 details.error
    apiMock.getFullIngestRecord.mockResolvedValue({
      id: 'ing-1',
      source: 'manual',
      status: 'failed',
      start_time: '2026-09-24T10:00:00.000Z',
      logs: [
        {
          id: 'log-llm-1',
          ingest_id: 'ing-1',
          stage: 'llm',
          operation: 'LLM归纳失败',
          details: { error: '[ValueError] 401 Unauthorized: invalid api key' },
          status: 'failed',
          error_message: '[ValueError] 401 Unauthorized: invalid api key',
          duration_ms: 12,
          timestamp: '2026-09-24T10:00:05.000Z',
        },
      ],
      builds: [],
    });

    render(<IngestPanel />);

    await waitFor(() => {
      expect(screen.getByText('详情')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('详情'));

    await waitFor(() => {
      // 失败原因必须显式展示出来，而不是只显示一句“失败”
      expect(screen.getByText('构建失败，原因如下')).toBeTruthy();
      expect(screen.getByText('构建失败')).toBeTruthy();
      // 汇总区与时间线详情都会展示该原因，允许出现多次
      expect(
        screen.getAllByText('[ValueError] 401 Unauthorized: invalid api key').length
      ).toBeGreaterThan(0);
    });
  });

  it('falls back to a hint when the backend provides no error text', async () => {
    const shared = await import('@/modules/shared');
    const apiMock = shared.api as unknown as Record<string, ReturnType<typeof vi.fn>>;

    apiMock.getIngestHistory.mockResolvedValue([
      {
        id: 'ing-2',
        source: 'manual',
        status: 'failed',
        record_count: 1,
        processed_count: 0,
        failed_count: 1,
        start_time: '2026-09-24T10:00:00.000Z',
        build_status: 'failed',
        builds: [],
      },
    ]);

    apiMock.getFullIngestRecord.mockResolvedValue({
      id: 'ing-2',
      source: 'manual',
      status: 'failed',
      start_time: '2026-09-24T10:00:00.000Z',
      logs: [
        {
          id: 'log-llm-2',
          ingest_id: 'ing-2',
          stage: 'llm',
          operation: 'LLM归纳失败',
          details: {},
          status: 'failed',
          duration_ms: 5,
          timestamp: '2026-09-24T10:00:05.000Z',
        },
      ],
      builds: [],
    });

    render(<IngestPanel />);

    await waitFor(() => {
      expect(screen.getByText('详情')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('详情'));

    await waitFor(() => {
      expect(screen.getByText('构建失败，原因如下')).toBeTruthy();
      expect(
        screen.getAllByText('未提供具体错误信息，请查看服务端日志').length
      ).toBeGreaterThan(0);
    });
  });
});

describe('getLogError', () => {
  it('prefers the top-level error_message', () => {
    expect(getLogError({ error_message: 'E1', details: { error: 'E2' } })).toBe('E1');
  });

  it('falls back to details.error when error_message is absent', () => {
    expect(getLogError({ details: { error: 'E2' } })).toBe('E2');
  });

  it('returns undefined when neither source has an error', () => {
    expect(getLogError({ details: { input: { a: 1 } } })).toBeUndefined();
  });

  it('ignores a non-string details.error', () => {
    expect(getLogError({ details: { error: { nested: true } } })).toBeUndefined();
  });
});
