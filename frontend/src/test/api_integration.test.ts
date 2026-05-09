/**
 * 前端 API 服务集成测试
 * 测试所有 API 调用方法的参数构建、请求格式和响应处理
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { apiService } from '@/modules/shared/services/api'

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
      workspaces: [{ id: 'ws-1', name: '测试空间', description: '描述' }],
      total: 1,
    })

    const result = await apiService.listWorkspaces()
    expect(result.workspaces).toHaveLength(1)
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/workspaces`
    )
  })

  it('创建工作空间', async () => {
    mockFetchResponse({
      workspace_id: 'ws-new',
      name: '新工作空间',
      status: 'created',
    }, 201)

    const result = await apiService.createWorkspace({
      name: '新工作空间',
      description: '测试创建',
      isolation_strategy: 'soft',
    })

    expect(result.workspace_id).toBe('ws-new')
    const [url, options] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe(`${API_BASE}/api/workspaces`)
    const body = JSON.parse(options.body)
    expect(body.name).toBe('新工作空间')
  })

  it('获取工作空间详情', async () => {
    mockFetchResponse({
      workspace_id: 'ws-1',
      name: '工作空间1',
      description: '测试',
    })

    const result = await apiService.getWorkspace('ws-1')
    expect(result.name).toBe('工作空间1')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/workspaces/ws-1`
    )
  })

  it('更新工作空间', async () => {
    mockFetchResponse({ workspace_id: 'ws-1', status: 'updated' })
    const result = await apiService.updateWorkspace('ws-1', {
      name: '更新名称',
    })
    expect(result.status).toBe('updated')
  })

  it('删除工作空间', async () => {
    mockFetchResponse({ status: 'deleted' })
    const result = await apiService.deleteWorkspace('ws-1')
    expect(result.status).toBe('deleted')
  })

  it('导入工作空间', async () => {
    mockFetchResponse({ workspace_id: 'ws-import', status: 'imported' }, 201)
    const result = await apiService.importWorkspace({
      name: '导入空间',
      export_data: { entities: [], relationships: [] },
    })
    expect(result.status).toBe('imported')
  })

  it('导出工作空间', async () => {
    mockFetchResponse({ export_data: { entities: [] } })
    const result = await apiService.exportWorkspace('ws-1')
    expect(result.export_data).toBeDefined()
  })

  it('处理API错误', async () => {
    mockFetchError(404, 'Workspace not found')
    await expect(apiService.getWorkspace('nonexistent')).rejects.toThrow()
  })
})

describe('场景管理 API', () => {
  it('创建场景', async () => {
    mockFetchResponse({
      status: 'created',
      scenario_id: 'scn-new',
      name: '新场景',
    }, 201)

    const result = await apiService.createScenario({
      name: '新场景',
      description: '场景描述',
    })
    expect(result.scenario_id).toBe('scn-new')
  })

  it('获取场景列表', async () => {
    mockFetchResponse({
      scenarios: [{ scenario_id: 'scn-1', name: '场景1' }],
    })
    const result = await apiService.listScenarios('ws-1')
    expect(result.scenarios).toHaveLength(1)
  })

  it('获取场景详情', async () => {
    mockFetchResponse({ scenario_id: 'scn-1', name: '场景1', description: 'desc' })
    const result = await apiService.getScenario('scn-1')
    expect(result.name).toBe('场景1')
  })

  it('更新场景', async () => {
    mockFetchResponse({ status: 'updated' })
    const result = await apiService.updateScenario('scn-1', { name: '更新场景' })
    expect(result.status).toBe('updated')
  })

  it('删除场景', async () => {
    mockFetchResponse({ status: 'deleted' })
    const result = await apiService.deleteScenario('scn-1')
    expect(result.status).toBe('deleted')
  })
})

describe('本体摄入 API', () => {
  it('文本摄入', async () => {
    mockFetchResponse({
      status: 'success',
      task_id: 'task-1',
      entities_found: 5,
    })
    const result = await apiService.ingestText({
      text: '测试军事事件',
      source: 'test',
      scenario_id: 'scn-1',
      workspace_id: 'ws-1',
    })
    expect(result.entities_found).toBe(5)
  })

  it('JSON摄入', async () => {
    mockFetchResponse({ status: 'success', entities_found: 3 })
    const result = await apiService.ingestJson({
      data: { event: 'test' },
      source: 'test',
      scenario_id: 'scn-1',
    })
    expect(result.status).toBe('success')
  })

  it('手动录入', async () => {
    mockFetchResponse({ status: 'success', entities_found: 2 })
    const result = await apiService.ingestManual({
      entities: [{ name: 'E1', type: 'Unit' }],
      relationships: [],
      scenario_id: 'scn-1',
    })
    expect(result.entities_found).toBe(2)
  })

  it('自然语言摄入', async () => {
    mockFetchResponse({ status: 'success', task_id: 'task-nl' })
    const result = await apiService.ingestNaturalLanguage({
      text: '太平洋舰队进行演习',
      scenario_id: 'scn-1',
      role: 'analyst',
    })
    expect(result.task_id).toBe('task-nl')
  })

  it('构建本体', async () => {
    mockFetchResponse({ status: 'started', task_id: 'build-1' })
    const result = await apiService.buildOntology({
      scenario_id: 'scn-1',
      run_async: true,
    })
    expect(result.status).toBe('started')
  })

  it('获取构建进度', async () => {
    mockFetchResponse({
      task_id: 'build-1',
      status: 'running',
      progress: 0.5,
      steps_completed: 3,
      steps_total: 6,
    })
    const result = await apiService.getBuildProgress('build-1')
    expect(result.progress).toBe(0.5)
  })

  it('获取构建历史', async () => {
    mockFetchResponse({ builds: [{ task_id: 'b-1', status: 'completed' }] })
    const result = await apiService.getBuildHistory(10)
    expect(result.builds).toBeDefined()
  })

  it('取消构建', async () => {
    mockFetchResponse({ status: 'cancelled' })
    const result = await apiService.cancelBuild('build-1')
    expect(result.status).toBe('cancelled')
  })
})

describe('智能问答 API', () => {
  it('提交问题', async () => {
    mockFetchResponse({
      session_id: 'q-session-1',
      answer: '当前太平洋区域有美军第7舰队部署。',
      confidence: 0.85,
      sources: ['source-1'],
      processing_time_ms: 250,
    })
    const result = await apiService.askQuestion({
      question: '当前太平洋区域有哪些军事部署？',
      role: 'analyst',
      scenario_id: 'scn-1',
    })
    expect(result.answer).toContain('太平洋')
    expect(result.confidence).toBeGreaterThan(0.5)
  })

  it('获取问答历史', async () => {
    mockFetchResponse({
      history: [
        { question: 'Q1', answer: 'A1', timestamp: '2024-01-01T00:00:00Z' },
      ],
      total: 1,
    })
    const result = await apiService.getQAHistory('ws-1', 'analyst', 10)
    expect(result.history).toHaveLength(1)
  })

  it('获取问答会话列表', async () => {
    mockFetchResponse({ sessions: [{ session_id: 's-1' }], total: 1 })
    const result = await apiService.getQASessions('ws-1', 10)
    expect(result.total).toBe(1)
  })

  it('获取问答会话详情', async () => {
    mockFetchResponse({
      session_id: 's-1',
      messages: [{ role: 'user', content: 'Q' }],
      total: 1,
    })
    const result = await apiService.getQASession('s-1')
    expect(result.messages).toHaveLength(1)
  })

  it('关闭问答会话', async () => {
    mockFetchResponse({ status: 'closed', session_id: 's-1' })
    const result = await apiService.closeQASession('s-1')
    expect(result.status).toBe('closed')
  })

  it('获取问答会话历史', async () => {
    mockFetchResponse({ session_id: 's-1', history: [], total: 0 })
    const result = await apiService.getQAHistory('s-1', 50)
    expect(result.total).toBe(0)
  })

  it('提交问答反馈', async () => {
    mockFetchResponse({ status: 'ok', feedback_id: 'fb-1' }, 201)
    const result = await apiService.submitQAFeedback('s-1', { helpful: true }, 5)
    expect(result.status).toBe('ok')
  })

  it('获取问答统计', async () => {
    mockFetchResponse({
      total: 100,
      today: 10,
      by_intent: { analysis: 50 },
      by_source: { web: 80 },
      time_distribution: {},
      period: { start: null, end: null },
    })
    const result = await apiService.getQAStats()
    expect(result.total).toBe(100)
  })

  it('获取用户问答统计', async () => {
    mockFetchResponse({ user_stats: [], total_users: 0, limit: 10 })
    const result = await apiService.getUserQAStats()
    expect(result.total_users).toBe(0)
  })

  it('获取话题统计', async () => {
    mockFetchResponse({ topics: [], limit: 20 })
    const result = await apiService.getTopicStats()
    expect(result.limit).toBe(20)
  })
})

describe('审计日志 API', () => {
  it('获取审计日志列表', async () => {
    mockFetchResponse({
      logs: [
        {
          event_id: 'ev-1',
          event_type: 'create',
          description: '创建场景',
          timestamp: '2024-01-01T00:00:00Z',
        },
      ],
      total: 1,
    })
    const result = await apiService.listAuditLogs({
      limit: 10,
      offset: 0,
    })
    expect(result.logs).toHaveLength(1)
  })

  it('获取特定日志详情', async () => {
    mockFetchResponse({
      event_id: 'ev-1',
      event_type: 'create',
      description: '创建场景',
      details: { user: 'admin' },
      timestamp: '2024-01-01T00:00:00Z',
    })
    const result = await apiService.getAuditLog('ev-1')
    expect(result.event_type).toBe('create')
  })

  it('获取审计时间线', async () => {
    mockFetchResponse({
      timeline: [{ event_id: 'ev-1', timestamp: '2024-01-01T00:00:00Z' }],
    })
    const result = await apiService.getAuditTimeline({
      limit: 20,
      offset: 0,
    })
    expect(result.timeline).toBeDefined()
  })

  it('获取审计统计', async () => {
    mockFetchResponse({
      total_events: 50,
      by_type: { create: 30, update: 20 },
      pending_anomalies: 2,
    })
    const result = await apiService.getAuditStats('ws-1')
    expect(result.total_events).toBe(50)
  })

  it('按事件类型筛选审计日志', async () => {
    mockFetchResponse({ logs: [], total: 0 })
    const result = await apiService.listAuditLogs({
      event_type: 'create',
      limit: 10,
    })
    expect(result.logs).toBeDefined()
  })

  it('带时间范围的审计日志查询', async () => {
    mockFetchResponse({ logs: [], total: 0 })
    const result = await apiService.listAuditLogs({
      start_time: '2024-01-01T00:00:00Z',
      end_time: '2024-12-31T23:59:59Z',
      limit: 20,
    })
    expect(result.logs).toBeDefined()
  })
})

describe('事件模拟器 API', () => {
  it('获取事件模板列表', async () => {
    mockFetchResponse({
      templates: [
        {
          template_id: 'tpl-1',
          name: '军事冲突模板',
          description: '标准军事冲突',
          event_type: 'military_movement',
          parameters: {},
        },
      ],
      total: 1,
    })
    const result = await apiService.getEventTemplates()
    expect(result.templates).toHaveLength(1)
  })

  it('创建事件模板', async () => {
    mockFetchResponse({
      template_id: 'tpl-new',
      name: '新模板',
      event_type: 'diplomatic_signal',
      created_at: '2024-01-01T00:00:00Z',
    }, 201)
    const result = await apiService.createEventTemplate({
      name: '新模板',
      description: '外交信号模板',
      event_type: 'diplomatic_signal',
      parameters: { intensity: 'low' },
    })
    expect(result.template_id).toBe('tpl-new')
  })

  it('生成模拟事件', async () => {
    mockFetchResponse({
      task_id: 'gen-1',
      events_generated: 5,
      events: [
        {
          event_id: 'ev-1',
          type: 'military_movement',
          description: '部队调动',
          timestamp: '2024-01-01T00:00:00Z',
          status: 'pending',
        },
      ],
    })
    const result = await apiService.generateEvents({
      count: 5,
      event_types: ['military_movement'],
      region: '中东',
    })
    expect(result.events_generated).toBe(5)
  })

  it('采纳事件', async () => {
    mockFetchResponse({
      status: 'ok',
      event_id: 'ev-1',
      message: '事件已采纳',
    })
    const result = await apiService.adoptEvent('ev-1', 'scn-default')
    expect(result.status).toBe('ok')
  })

  it('批量采纳事件', async () => {
    mockFetchResponse({
      status: 'ok',
      adopted_count: 3,
      failed_count: 0,
      results: [],
    })
    const result = await apiService.adoptEventsBulk(['ev-1', 'ev-2', 'ev-3'])
    expect(result.adopted_count).toBe(3)
  })

  it('列出模拟事件', async () => {
    mockFetchResponse({
      events: [],
      total: 0,
      limit: 50,
      offset: 0,
    })
    const result = await apiService.listSimulationEvents({
      status: 'pending',
      limit: 50,
    })
    expect(result.total).toBe(0)
  })

  it('时间控制 - 开始', async () => {
    mockFetchResponse({
      status: 'ok',
      action: 'start',
      current_time: '2024-01-01T00:00:00Z',
    })
    const result = await apiService.controlSimulationTime({ action: 'start' })
    expect(result.action).toBe('start')
  })

  it('时间控制 - 暂停', async () => {
    mockFetchResponse({ status: 'ok', action: 'pause' })
    const result = await apiService.controlSimulationTime({ action: 'pause' })
    expect(result.action).toBe('pause')
  })

  it('时间控制 - 设置速度', async () => {
    mockFetchResponse({
      status: 'ok',
      action: 'set_speed',
      speed: 10,
    })
    const result = await apiService.controlSimulationTime({
      action: 'set_speed',
      speed: 10,
    })
    expect(result.speed).toBe(10)
  })

  it('时间控制 - 停止', async () => {
    mockFetchResponse({ status: 'ok', action: 'stop' })
    const result = await apiService.controlSimulationTime({ action: 'stop' })
    expect(result.action).toBe('stop')
  })

  it('获取模拟状态', async () => {
    mockFetchResponse({
      status: 'running',
      current_time: '2024-01-01T00:00:00Z',
      speed: 1,
      events_generated: 100,
      events_adopted: 80,
      events_pending: 20,
    })
    const result = await apiService.getSimulationStatus()
    expect(result.status).toBe('running')
    expect(result.events_generated).toBe(100)
  })
})

describe('技能管理 API', () => {
  it('获取技能列表', async () => {
    mockFetchResponse({
      skills: [
        { skill_id: 'sk-1', name: 'skill1', type: 'tool', status: 'active', category: 'intel' },
      ],
      page: 1,
      page_size: 20,
      total: 1,
    })
    const result = await apiService.listSkills({ page: 1, page_size: 20 })
    expect(result.skills).toHaveLength(1)
  })

  it('扫描技能目录', async () => {
    mockFetchResponse({ skills: [], total: 0 })
    const result = await apiService.scanSkillsDirectory()
    expect(result.total).toBe(0)
  })

  it('获取全部技能', async () => {
    mockFetchResponse({
      registered: [],
      scanned: [],
      total_registered: 0,
      total_scanned: 0,
    })
    const result = await apiService.getAllSkills()
    expect(result.total_registered).toBe(0)
  })

  it('获取技能分类', async () => {
    mockFetchResponse({ categories: [{ name: 'intel', skill_count: 5, path: '/intel' }] })
    const result = await apiService.getSkillCategories()
    expect(result.categories).toHaveLength(1)
  })

  it('注册技能', async () => {
    mockFetchResponse({
      skill_id: 'sk-new',
      name: 'new-skill',
      type: 'tool',
      status: 'registered',
      created_at: '2024-01-01T00:00:00Z',
    }, 201)
    const result = await apiService.registerSkill({
      name: 'new-skill',
      skill_type: 'tool',
      description: '新技能',
      category: 'custom',
    })
    expect(result.skill_id).toBe('sk-new')
  })

  it('激活技能', async () => {
    mockFetchResponse({ skill_id: 'sk-1', status: 'active' })
    const result = await apiService.activateSkill('sk-1')
    expect(result.status).toBe('active')
  })

  it('停用技能', async () => {
    mockFetchResponse({ skill_id: 'sk-1', status: 'inactive' })
    const result = await apiService.deactivateSkill('sk-1')
    expect(result.status).toBe('inactive')
  })

  it('切换技能启用状态', async () => {
    mockFetchResponse({ status: 'ok', enabled: false })
    const result = await apiService.toggleSkill('sk-1', false)
    expect(result.enabled).toBe(false)
  })

  it('获取已加载技能', async () => {
    mockFetchResponse({ skills: ['sk-1', 'sk-2'] })
    const result = await apiService.getLoadedSkills()
    expect(result.skills).toHaveLength(2)
  })

  it('保存技能内容', async () => {
    mockFetchResponse({ status: 'saved', skill_id: 'sk-1' })
    const result = await apiService.saveSkillContent('custom-skill', 'custom', 'content')
    expect(result.status).toBe('saved')
  })
})

describe('角色管理 API', () => {
  it('获取角色列表', async () => {
    mockFetchResponse({
      roles: [
        { role_id: 'r-1', name: 'admin', description: '管理员', permissions: ['read', 'write'], created_at: '2024-01-01T00:00:00Z' },
      ],
      total: 1,
    })
    const result = await apiService.listRoles({ page: 1, page_size: 20 })
    expect(result.roles).toHaveLength(1)
  })

  it('创建角色', async () => {
    mockFetchResponse({
      role_id: 'r-new',
      name: 'analyst',
      description: '分析师',
      permissions: ['read'],
      created_at: '2024-01-01T00:00:00Z',
    }, 201)
    const result = await apiService.createRole({
      name: 'analyst',
      description: '分析师',
      permissions: ['read'],
    })
    expect(result.role_id).toBe('r-new')
  })

  it('更新角色', async () => {
    mockFetchResponse({
      role_id: 'r-1',
      name: 'updated',
      description: '已更新',
      permissions: ['read', 'write', 'delete'],
    })
    const result = await apiService.updateRole('r-1', {
      name: 'updated',
      permissions: ['read', 'write', 'delete'],
    })
    expect(result.permissions).toHaveLength(3)
  })

  it('删除角色', async () => {
    mockFetchResponse({ status: 'ok', message: '已删除' })
    const result = await apiService.deleteRole('r-1')
    expect(result.status).toBe('ok')
  })
})

describe('策略管理 API', () => {
  it('获取策略列表', async () => {
    mockFetchResponse({
      policies: [
        {
          policy_id: 'p-1',
          name: '访问控制',
          description: '描述',
          category: 'access_control',
          status: 'active',
          version: '1.0.0',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ],
      total: 1,
    })
    const result = await apiService.listPolicies({ status: 'active' })
    expect(result.policies).toHaveLength(1)
  })

  it('创建策略', async () => {
    mockFetchResponse({
      policy_id: 'p-new',
      name: '新策略',
      status: 'active',
      rego_content: 'package odap\n\ndefault allow = false',
    }, 201)
    const result = await apiService.createPolicy({
      name: '新策略',
      description: '新策略描述',
      markdown_content: '# 策略\n\n内容。',
      category: 'access_control',
    })
    expect(result.policy_id).toBe('p-new')
  })

  it('获取策略详情', async () => {
    mockFetchResponse({
      policy_id: 'p-1',
      name: '策略1',
      description: '描述',
      markdown_content: '# MD',
      rego_content: 'package odap',
      category: 'access',
      status: 'active',
      version: '1.0.0',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    })
    const result = await apiService.getPolicy('p-1')
    expect(result.name).toBe('策略1')
  })

  it('更新策略', async () => {
    mockFetchResponse({
      policy_id: 'p-1',
      name: '更新后策略',
      status: 'active',
      version: '1.1.0',
    })
    const result = await apiService.updatePolicy('p-1', {
      name: '更新后策略',
    })
    expect(result.version).toBe('1.1.0')
  })

  it('切换策略状态', async () => {
    mockFetchResponse({ policy_id: 'p-1', status: 'inactive' })
    const result = await apiService.togglePolicyStatus('p-1', false)
    expect(result.status).toBe('inactive')
  })
})

describe('代理系统 API', () => {
  it('初始化代理', async () => {
    mockFetchResponse({
      status: 'ok',
      agent_id: 'agent-1',
      tools_available: 10,
    })
    const result = await apiService.initAgent({ model: 'gpt-4' })
    expect(result.agent_id).toBe('agent-1')
  })

  it('运行代理', async () => {
    mockFetchResponse({
      status: 'ok',
      result: '分析完成',
      agent_id: 'agent-1',
      execution_time_ms: 500,
    })
    const result = await apiService.runAgent({
      input: '分析当前态势',
      workspace_id: 'ws-1',
    })
    expect(result.result).toBeDefined()
  })

  it('获取代理状态', async () => {
    mockFetchResponse({
      status: 'active',
      agents: [{ agent_id: 'a-1', type: 'analysis', status: 'idle' }],
    })
    const result = await apiService.getAgentStatus()
    expect(result.status).toBe('active')
  })

  it('列出代理工具', async () => {
    mockFetchResponse({
      tools: [{ name: 'search', description: '搜索工具', category: 'search' }],
      total: 1,
    })
    const result = await apiService.listAgentTools()
    expect(result.tools).toHaveLength(1)
  })

  it('代理对话', async () => {
    mockFetchResponse({
      session_id: 'chat-1',
      response: '根据分析，当前太平洋区域有美军3艘航母部署。',
      agent_type: 'analysis',
      thinking_steps: [{ step: '检索知识库', detail: '查询相关数据' }],
      tools_used: ['search'],
    })
    const result = await apiService.agentChat({
      message: '请分析当前太平洋区域部署情况',
      role: 'analyst',
    })
    expect(result.session_id).toBe('chat-1')
    expect(result.tools_used).toContain('search')
  })
})

describe('用户认知引擎 API', () => {
  it('识别意图', async () => {
    mockFetchResponse({
      intent: { type: 'analysis', confidence: 0.9 },
      knowledge_results: [],
      session_id: 'cog-1',
    })
    const result = await apiService.recognizeIntent('分析当前态势', 'analyst')
    expect(result.intent.type).toBe('analysis')
  })

  it('获取角色视图', async () => {
    mockFetchResponse({ role: 'analyst', view_type: 'military' })
    const result = await apiService.getRoleView('analyst')
    expect(result.role).toBe('analyst')
  })

  it('知识导航', async () => {
    mockFetchResponse({
      entity_id: 'e-1',
      navigation_path: ['e-1', 'e-2'],
      related_entities: [],
      entity_context: {},
    })
    const result = await apiService.navigateKnowledge('e-1', 'outbound')
    expect(result.entity_id).toBe('e-1')
  })

  it('解释决策', async () => {
    mockFetchResponse({
      explanation_id: 'exp-1',
      query: '为什么？',
      answer: '因为...',
      confidence: 0.8,
      reasoning_chain: [{ step_id: 's1', step_type: 'reasoning', description: '推理' }],
      sources: ['s-1'],
    })
    const result = await apiService.explainDecision('d-1', {})
    expect(result.confidence).toBeGreaterThan(0)
  })
})

describe('闭环反馈 API', () => {
  it('提交行动反馈', async () => {
    mockFetchResponse({ status: 'ok', feedback_id: 'fb-1', outcome: 'success' })
    const result = await apiService.submitActionFeedback({
      action_id: 'a-1',
      outcome: 'success',
      duration_ms: 100,
    })
    expect(result.outcome).toBe('success')
  })

  it('获取决策反馈', async () => {
    mockFetchResponse({
      decision_id: 'd-1',
      feedback_count: 3,
      feedbacks: [],
    })
    const result = await apiService.getDecisionFeedback('d-1')
    expect(result.feedback_count).toBe(3)
  })
})

describe('系统监控 API', () => {
  it('获取系统性能指标', async () => {
    mockFetchResponse({
      cpu_percent: 45.5,
      memory_percent: 60.2,
      disk_percent: 30.1,
      uptime_seconds: 86400,
      active_connections: 10,
      request_count: 1000,
      error_count: 5,
    })
    const result = await apiService.getSystemMetrics()
    expect(result.cpu_percent).toBeDefined()
    expect(result.memory_percent).toBeDefined()
  })

  it('获取系统健康状态', async () => {
    mockFetchResponse({
      status: 'healthy',
      openharness_v1: true,
      openharness_v2: {},
      version: '1.0.0',
    })
    const result = await apiService.getSystemHealth()
    expect(result.status).toBe('healthy')
  })
})

describe('API 错误处理', () => {
  it('处理网络错误', async () => {
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('Failed to fetch')
    )
    await expect(apiService.listWorkspaces()).rejects.toThrow('Failed to fetch')
  })

  it('处理404错误', async () => {
    mockFetchError(404, 'Not Found')
    await expect(apiService.getWorkspace('nonexistent')).rejects.toThrow()
  })

  it('处理500服务器错误', async () => {
    mockFetchError(500, 'Internal Server Error')
    await expect(apiService.listWorkspaces()).rejects.toThrow()
  })

  it('处理403权限错误', async () => {
    mockFetchError(403, 'Forbidden')
    await expect(apiService.createScenario({ name: 'test', description: 'test' })).rejects.toThrow()
  })

  it('处理401认证错误', async () => {
    mockFetchError(401, 'Unauthorized')
    await expect(apiService.listWorkspaces()).rejects.toThrow()
  })
})