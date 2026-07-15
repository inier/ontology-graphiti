import React from 'react'
import { vi } from 'vitest'
import '@testing-library/jest-dom/vitest'

globalThis.fetch = vi.fn() as unknown as typeof fetch

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}))

Element.prototype.scrollIntoView = vi.fn()

// ─── Sigma.js WebGL stub ───
// sigma.js references WebGL2RenderingContext and WebGLRenderingContext at module level,
// which do not exist in jsdom. Provide minimal stubs.
if (typeof (globalThis as Record<string, unknown>).WebGL2RenderingContext === 'undefined') {
  (globalThis as Record<string, unknown>).WebGL2RenderingContext = class WebGL2RenderingContext {};
}
if (typeof (globalThis as Record<string, unknown>).WebGLRenderingContext === 'undefined') {
  (globalThis as Record<string, unknown>).WebGLRenderingContext = class WebGLRenderingContext {};
}

// ─── @react-sigma/minimap stub ───
// MiniMap creates a second Sigma instance (WebGL) which won't work in jsdom.
// Mock the entire module so tests can import MinimapPanel without WebGL errors.
vi.mock('@react-sigma/minimap', () => ({
  MiniMap: () => null,
}))

vi.mock('@/config', () => ({
  API_BASE: 'http://localhost:8000',
}))
