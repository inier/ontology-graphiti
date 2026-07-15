import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QAPanel } from './QAPanel';

vi.mock('@/config', () => ({
  API_BASE: 'http://localhost:8000',
}));

describe('QAPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockReset();
  });

  it('renders without crashing', () => {
    const { container } = render(<QAPanel />);
    expect(container).toBeTruthy();
  });

  it('displays placeholder text in input', () => {
    render(<QAPanel />);
    expect(screen.getByPlaceholderText(/Ask a question/)).toBeTruthy();
  });

  it('send button is disabled when input is empty', () => {
    render(<QAPanel />);
    const sendBtn = screen.getByRole('button', { name: /send/i });
    expect(sendBtn).toBeDisabled();
  });

  it('allows typing in the text area', () => {
    render(<QAPanel />);
    const textArea = screen.getByPlaceholderText(/Ask a question/);
    fireEvent.change(textArea, { target: { value: '什么是本体?' } });
    expect(textArea).toHaveValue('什么是本体?');
  });

  it('enables send button when input has text', () => {
    render(<QAPanel />);
    const textArea = screen.getByPlaceholderText(/Ask a question/);
    fireEvent.change(textArea, { target: { value: '什么是本体?' } });
    const sendBtn = screen.getByRole('button', { name: /send/i });
    expect(sendBtn).not.toBeDisabled();
  });

  it('sends message and displays user message on send', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ answer: '本体是知识图谱的核心概念', sources: [] }),
    });

    render(<QAPanel />);
    const textArea = screen.getByPlaceholderText(/Ask a question/);
    fireEvent.change(textArea, { target: { value: '什么是本体?' } });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));

    expect(screen.getByText('什么是本体?')).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByText('本体是知识图谱的核心概念')).toBeTruthy();
    });
  });

  it('displays error message when fetch fails', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('Network error')
    );

    render(<QAPanel />);
    const textArea = screen.getByPlaceholderText(/Ask a question/);
    fireEvent.change(textArea, { target: { value: '测试问题' } });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText('Failed to get answer. Please try again.')).toBeTruthy();
    });
  });
});
