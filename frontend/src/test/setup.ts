import '@testing-library/jest-dom/vitest'

globalThis.fetch = vi.fn() as unknown as typeof fetch

vi.mock('@/config', () => ({
  API_BASE: 'http://localhost:8000',
}))