import { describe, it, expect, vi } from 'vitest'

vi.mock('@/config', () => ({
  API_BASE: 'http://localhost:8000',
}))

describe('配置模块', () => {
  it('导出 API_BASE 常量', async () => {
    const config = await import('@/config')
    expect(config.API_BASE).toBe('http://localhost:8000')
  })
})

describe('API 服务模块', () => {
  it('导出 api 对象及核心方法', async () => {
    const { api } = await import('@/modules/shared/services/api')
    expect(api).toBeDefined()
    expect(typeof api.listWorkspaces).toBe('function')
    expect(typeof api.getHealth).toBe('function')
    expect(typeof api.listAuditEvents).toBe('function')
    expect(typeof api.askQuestion).toBe('function')
    expect(typeof api.listSkills).toBe('function')
    expect(typeof api.listRoles).toBe('function')
    expect(typeof api.listPolicies).toBe('function')
  })
})

describe('共享类型模块', () => {
  it('导出类型定义', async () => {
    const types = await import('@/modules/shared/types')
    expect(types).toBeDefined()
  })
})

describe('共享 Store 模块', () => {
  it('导出 useAppStore 和 useAuditStore', async () => {
    const stores = await import('@/modules/shared/stores')
    expect(stores.useAppStore).toBeDefined()
    expect(stores.useAuditStore).toBeDefined()
  })
})
