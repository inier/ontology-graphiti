import { describe, it, expect, beforeEach, vi } from 'vitest'
import { api } from '@/modules/shared/services/api'

const API_BASE = 'http://localhost:8000'

function mockFetchResponse(data: unknown, status = 200) {
  ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as Response)
}

function mockFetchError(status: number, message: string) {
  ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: false,
    status,
    statusText: message,
    json: () => Promise.resolve({ detail: message }),
  } as Response)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('工作空间管理 API', () => {
  it('获取工作空间列表', async () => {
    mockFetchResponse({
      workspaces: [
        { workspace_id: 'ws-1', name: '测试空间', description: '描述', type: 'default', status: 'active', owner: 'admin', created_at: '2026-01-01' },
      ],
    })

    const result = await api.listWorkspaces()
    expect(Array.isArray(result)).toBe(true)
    expect(result.length).toBeGreaterThanOrEqual(1)
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/workspaces`,
      expect.anything()
    )
  })

  it('创建工作空间', async () => {
    mockFetchResponse({
      workspace_id: 'ws-new',
      name: '新工作空间',
      description: '',
      type: 'default',
      status: 'active',
      owner: 'admin',
      created_at: '2026-01-01',
    })

    const result = await api.createWorkspace({ name: '新工作空间' })
    expect(result.name).toBe('新工作空间')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/workspaces`,
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('获取单个工作空间', async () => {
    mockFetchResponse({
      workspace_id: 'ws-1',
      name: '测试空间',
      description: '描述',
      type: 'default',
      status: 'active',
      owner: 'admin',
      created_at: '2026-01-01',
    })

    const result = await api.getWorkspace('ws-1')
    expect(result.workspace_id).toBe('ws-1')
  })

  it('更新工作空间', async () => {
    mockFetchResponse({
      workspace_id: 'ws-1',
      name: '更新后',
      description: '新描述',
      type: 'default',
      status: 'active',
      owner: 'admin',
      created_at: '2026-01-01',
    })

    const result = await api.updateWorkspace('ws-1', { name: '更新后' })
    expect(result.name).toBe('更新后')
  })

  it('删除工作空间', async () => {
    mockFetchResponse({ status: 'success', message: '已删除' })

    const result = await api.deleteWorkspace('ws-1')
    expect(result.status).toBe('success')
  })
})

describe('本体摄入 API', () => {
  it('文本摄入', async () => {
    mockFetchResponse({ success: true, task_id: 'task-001' })

    const result = await api.ingestText('测试文本', 'scenario-001')
    expect(result.success).toBe(true)
    expect(result.task_id).toBe('task-001')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/ingest/text`,
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('新闻摄入', async () => {
    mockFetchResponse({ success: true, task_id: 'task-002' })

    const result = await api.ingestNews('https://example.com/news', 'scenario-001')
    expect(result.success).toBe(true)
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/ingest/news`,
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('随机事件生成', async () => {
    mockFetchResponse({ success: true, doc_count: 2, versions: ['v1'] })

    const result = await api.ingestRandom('scenario-001')
    expect(result.success).toBe(true)
    expect(result.doc_count).toBe(2)
  })

  it('获取摄入状态', async () => {
    mockFetchResponse({
      id: 'ingest-001',
      source: 'text',
      status: 'completed',
      record_count: 1,
      processed_count: 1,
      failed_count: 0,
      start_time: '2026-01-01T00:00:00Z',
    })

    const result = await api.getIngestStatus('ingest-001')
    expect(result.id).toBe('ingest-001')
    expect(result.status).toBe('completed')
  })

  it('获取摄入历史', async () => {
    mockFetchResponse([])

    const result = await api.getIngestHistory(10)
    expect(Array.isArray(result)).toBe(true)
  })
})

describe('版本管理 API', () => {
  it('列出版本', async () => {
    mockFetchResponse([
      { version_id: 'v1', scenario_id: 'scenario-001', created_at: '2026-01-01', commit_message: '初始版本' },
    ])

    const result = await api.getVersions('scenario-001')
    expect(Array.isArray(result)).toBe(true)
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining(`${API_BASE}/api/ontology/ingest/versions`),
      expect.anything()
    )
  })

  it('版本回滚', async () => {
    mockFetchResponse({ status: 'success', version_id: 'v1', message: '已回滚' })

    const result = await api.rollbackVersion('v1', 'scenario-001')
    expect(result.status).toBe('success')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining(`${API_BASE}/api/ontology/ingest/versions/rollback`),
      expect.objectContaining({ method: 'POST' })
    )
  })
})

describe('审计日志 API', () => {
  it('列出审计事件', async () => {
    mockFetchResponse({
      events: [
        {
          id: 'evt-001',
          timestamp: '2026-01-01T00:00:00Z',
          event_type: 'user.login',
          severity: 'info',
          actor_id: 'user-001',
          actor_name: '测试用户',
          action: 'login',
          resource_type: 'system',
          resource_id: 'auth',
          result_status: 'success',
          result_message: '登录成功',
          workspace_id: 'default',
          trace_id: 'trace-001',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    })

    const result = await api.listAuditEvents({ page: 1, page_size: 20 })
    expect(result.events).toHaveLength(1)
  })

  it('获取审计统计', async () => {
    mockFetchResponse({
      total: 100,
      by_severity: { info: 80, warn: 15, error: 5 },
      by_type: { 'user.login': 50, 'data.ingest': 30 },
      by_status: { success: 90, failure: 10 },
    })

    const result = await api.getAuditStats()
    expect(result.total).toBe(100)
  })
})

describe('智能问答 API', () => {
  it('提问', async () => {
    mockFetchResponse({
      answer: '这是回答',
      session_id: 'session-001',
      sources: [],
      intent: 'query',
    })

    const result = await api.askQuestion('测试问题', undefined, 'default')
    expect(result.answer).toBe('这是回答')
    expect(result.session_id).toBe('session-001')
  })

  it('列出会话', async () => {
    mockFetchResponse({ sessions: [], total: 0, limit: 50 })

    const result = await api.listQASessions()
    expect(result.sessions).toHaveLength(0)
  })
})

describe('技能管理 API', () => {
  it('列出技能', async () => {
    mockFetchResponse({ skills: [], total: 0, page: 1, page_size: 10 })

    const result = await api.listSkills()
    expect(result.skills).toHaveLength(0)
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/skill/skills`,
      expect.anything()
    )
  })

  it('获取已加载技能', async () => {
    mockFetchResponse({ skills: ['skill-1'] })

    const result = await api.getLoadedSkills()
    expect(result.skills).toHaveLength(1)
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/skill/skills/loaded`,
      expect.anything()
    )
  })

  it('激活技能', async () => {
    mockFetchResponse({ skill_id: 'skill-001', status: 'active' })

    const result = await api.activateSkill('skill-001')
    expect(result.status).toBe('active')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/skill/skills/skill-001/activate`,
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('停用技能', async () => {
    mockFetchResponse({ skill_id: 'skill-001', status: 'inactive' })

    const result = await api.deactivateSkill('skill-001')
    expect(result.status).toBe('inactive')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/skill/skills/skill-001/deactivate`,
      expect.objectContaining({ method: 'POST' })
    )
  })
})

describe('角色管理 API', () => {
  it('列出角色', async () => {
    mockFetchResponse([
      { id: '1', name: '系统管理员', description: '管理员', role_type: 'system_admin', permissions: ['p1'], created_at: '2026-01-01' },
    ])

    const result = await api.listRoles()
    expect(result.roles).toHaveLength(1)
    expect(result.roles[0].name).toBe('系统管理员')
    expect(result.total).toBe(1)
  })
})

describe('策略管理 API', () => {
  it('列出策略', async () => {
    mockFetchResponse({
      policies: [
        { policy_id: 'p-1', name: '访问控制策略', description: '描述', category: 'access_control', status: 'enabled', version: '1.0.0', updated_at: '2026-01-01' },
      ],
      total: 1,
    })

    const result = await api.listPolicies()
    expect(result.policies).toHaveLength(1)
    expect(result.total).toBe(1)
  })
})

describe('事件模拟器 API', () => {
  it('获取事件模板', async () => {
    mockFetchResponse({ templates: [], total: 0 })

    const result = await api.getEventTemplates()
    expect(result.templates).toHaveLength(0)
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/templates`,
      expect.anything()
    )
  })

  it('生成事件', async () => {
    mockFetchResponse({ task_id: 'task-001', events_generated: 5, events: [] })

    const result = await api.generateEvents({ template_id: 'tpl-001', count: 5 })
    expect(result.task_id).toBe('task-001')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/generate`,
      expect.objectContaining({ method: 'POST' })
    )
  })
})

describe('系统监控 API', () => {
  it('健康检查', async () => {
    mockFetchResponse({ status: 'healthy', version: '2.0.0' })

    const result = await api.getHealth()
    expect(result.status).toBe('healthy')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/health`,
      expect.anything()
    )
  })
})

describe('API 错误处理', () => {
  it('404 错误', async () => {
    mockFetchError(404, 'Not Found')

    await expect(api.getWorkspace('nonexistent')).rejects.toThrow('HTTP 404')
  })

  it('500 错误', async () => {
    mockFetchError(500, 'Internal Server Error')

    await expect(api.getWorkspace('ws-1')).rejects.toThrow('HTTP 500')
  })

  it('400 错误', async () => {
    mockFetchError(400, 'Bad Request')

    await expect(api.createWorkspace({ name: '' })).rejects.toThrow('HTTP 400')
  })
})
