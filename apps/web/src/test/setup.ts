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

// ResizeObserver mock — 必须用 class（可被 `new` 调用）。
// 之前用 vi.fn().mockImplementation(() => ({...})) 是箭头函数，不能 `new`，
// 导致 @rc-component/resize-observer 调 `new ResizeObserver()` 报
// "() => ({...}) is not a constructor"（IngestPanel 9 个测试全挂）。
class ResizeObserverMock {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver

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

// ─── i18n 初始化 ───
// 项目采用"中文作为 key"的国际化方案（见 project_memory）。
// 组件用 t('搜索实体') 包裹，测试需 getByText('搜索实体') 匹配。
// 测试环境 resources 留空，react-i18next 默认 fallback 会返回 key 本身（即中文），
// 使 GraphToolbar 等 i18n 组件的断言能通过。
//
// 但 OntologyBuildProgress 等组件使用英文 dot-notation 键（如 buildProgress.statusCompleted），
// 对应 locale 文件中的扁平键。需加载 'ontology' 命名空间并设 keySeparator: false，
// 否则 i18next 默认用 '.' 分隔会查嵌套路径而找不到扁平键。
import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'
import ontologyZhCN from '../modules/ontology/locales/zh-CN/ontology.json'

void i18next.use(initReactI18next).init({
  lng: 'zh-CN',
  resources: {
    'zh-CN': {
      translation: {},
      ontology: ontologyZhCN,
    },
  },
  ns: ['translation', 'ontology'],
  defaultNS: 'translation',
  keySeparator: false,
  interpolation: { escapeValue: false },
})
