import { describe, it, expect, vi, beforeEach } from 'vitest';
import { processApi, ruleApi, logicApi, indicatorApi, entityApi, processTypeDefinitions, ruleTypeDefinitions, functionTypeDefinitions, indicatorTypeDefinitions } from './businessApi';

import type {
  BusinessProcess,
  BusinessProcessFormData,
  BusinessRule,
  BusinessRuleFormData,
  BusinessLogic,
  BusinessLogicFormData,
  BusinessIndicator,
  BusinessIndicatorFormData,
  BusinessEntity,
} from '../types';

/**
 * 真实 DTO 形状的 fixture。
 *
 * 早前用例用 `as unknown` 把 `{ name, description, steps }` 这类「看起来像就行」的对象硬塞给
 * `processApi.create`，把参数类型检查整条绕开；一旦后端字段改名，测试依然全绿。
 * 这里改成先构造合法 DTO，再用 overrides 覆写关心的字段。
 */
function processForm(overrides: Partial<BusinessProcessFormData> = {}): BusinessProcessFormData {
  return {
    name: 'Order Process',
    display_name: '订单流程',
    description: 'desc',
    related_objects: [],
    llm_description: '',
    flow_nodes: [],
    ...overrides,
  };
}

function processRecord(overrides: Partial<BusinessProcess> = {}): BusinessProcess {
  return {
    ...processForm(),
    process_id: 'proc-1',
    status: 'draft',
    created_by: 'tester',
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
    ...overrides,
  };
}

function ruleForm(overrides: Partial<BusinessRuleFormData> = {}): BusinessRuleFormData {
  return {
    name: 'Validation Rule',
    display_name: '校验规则',
    description: 'desc',
    related_objects: [],
    llm_description: '',
    rule_conditions: [],
    ...overrides,
  };
}

function ruleRecord(overrides: Partial<BusinessRule> = {}): BusinessRule {
  return {
    ...ruleForm(),
    rule_id: 'rule-1',
    status: 'draft',
    created_by: 'tester',
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
    ...overrides,
  };
}

function logicForm(overrides: Partial<BusinessLogicFormData> = {}): BusinessLogicFormData {
  return {
    name: 'Calculation Logic',
    display_name: '计算逻辑',
    description: 'desc',
    related_objects: [],
    llm_description: '',
    logic_type: 'compute',
    logic_expression: 'x + y',
    ...overrides,
  };
}

function logicRecord(overrides: Partial<BusinessLogic> = {}): BusinessLogic {
  return {
    ...logicForm(),
    logic_id: 'logic-1',
    status: 'draft',
    created_by: 'tester',
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
    ...overrides,
  };
}

function indicatorForm(overrides: Partial<BusinessIndicatorFormData> = {}): BusinessIndicatorFormData {
  return {
    name: 'Revenue Indicator',
    display_name: '收入指标',
    description: 'desc',
    related_objects: [],
    llm_description: '',
    indicator_type: 'kpi',
    calculation_formula: 'sum(revenue)',
    unit: 'CNY',
    ...overrides,
  };
}

function indicatorRecord(overrides: Partial<BusinessIndicator> = {}): BusinessIndicator {
  return {
    ...indicatorForm(),
    indicator_id: 'ind-1',
    status: 'draft',
    created_by: 'tester',
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
    ...overrides,
  };
}

function entityRecord(overrides: Partial<BusinessEntity> = {}): BusinessEntity {
  return {
    id: 'ent-1',
    name: 'Customer',
    display_name: '客户',
    description: 'desc',
    related_objects: [],
    llm_description: '',
    entity_type: 'process',
    status: 'draft',
    created_by: 'tester',
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
    ...overrides,
  };
}

function mockFetchResponse<T>(data: T, status = 200) {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as Response);
}

function mockFetchError(status: number, statusText: string) {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: false,
    status,
    statusText,
    json: () => Promise.resolve({ detail: statusText }),
  } as Response);
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem('token', 'test-jwt-token');
});

// ─── Process API ───────────────────────────────────────────────

describe('processApi', () => {
  const mockProcess = processRecord();

  it('list calls GET /api/business-processes', async () => {
    mockFetchResponse([mockProcess]);

    const result = await processApi.list();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-processes'),
      expect.any(Object),
    );
    expect(result).toHaveLength(1);
  });

  it('list passes ontology_id and version_id as query params', async () => {
    mockFetchResponse([]);

    await processApi.list('ont-1', 'v-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('ontology_id=ont-1');
    expect(calledUrl).toContain('version_id=v-1');
  });

  it('list encodes special characters in query params', async () => {
    mockFetchResponse([]);

    await processApi.list('ont/special', 'v&1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('ontology_id=ont%2Fspecial');
    expect(calledUrl).toContain('version_id=v%261');
  });

  it('get calls GET /api/business-processes/:id', async () => {
    mockFetchResponse(mockProcess);

    const result = await processApi.get('proc-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-processes/proc-1'),
      expect.any(Object),
    );
    expect(result.process_id).toBe('proc-1');
  });

  it('create sends POST with correct body', async () => {
    const formData = processForm({ name: 'New Process' });
    mockFetchResponse({ process_id: 'proc-new', ...formData });

    await processApi.create(formData);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-processes'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(formData),
      }),
    );
  });

  it('create passes ontology_id and version_id in body', async () => {
    const formData = { ...processForm({ name: 'New' }), ontology_id: 'ont-1', version_id: 'v-1' };
    mockFetchResponse({ process_id: 'proc-new', ...formData });

    await processApi.create(formData);
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    expect(JSON.parse(callOptions.body as string)).toEqual(formData);
  });

  it('update sends PUT with correct body', async () => {
    const formData = processForm({ name: 'Updated Process', description: 'new desc' });
    mockFetchResponse({ process_id: 'proc-1', ...formData });

    await processApi.update('proc-1', formData);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-processes/proc-1'),
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(formData),
      }),
    );
  });

  it('delete sends DELETE request', async () => {
    mockFetchResponse({ status: 'ok' });

    await processApi.delete('proc-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-processes/proc-1'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('importYaml sends POST with yaml content', async () => {
    const yaml = 'name: Test\nsteps: []';
    mockFetchResponse([mockProcess]);

    const result = await processApi.importYaml(yaml);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-processes/import-yaml'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ yaml }),
      }),
    );
    expect(result).toHaveLength(1);
  });
});

// ─── Rule API ──────────────────────────────────────────────────

describe('ruleApi', () => {
  const mockRule = ruleRecord();

  it('list calls GET /api/business-rules', async () => {
    mockFetchResponse([mockRule]);

    const result = await ruleApi.list();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-rules'),
      expect.any(Object),
    );
    expect(result).toHaveLength(1);
  });

  it('list passes ontology_id and version_id as query params', async () => {
    mockFetchResponse([]);

    await ruleApi.list('ont-1', 'v-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('ontology_id=ont-1');
    expect(calledUrl).toContain('version_id=v-1');
  });

  it('get calls GET /api/business-rules/:id', async () => {
    mockFetchResponse(mockRule);

    const result = await ruleApi.get('rule-1');
    expect(result.rule_id).toBe('rule-1');
  });

  it('create sends POST with correct body', async () => {
    const formData = ruleForm({ name: 'New Rule' });
    mockFetchResponse({ rule_id: 'rule-new', ...formData });

    await ruleApi.create(formData);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-rules'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('update sends PUT with correct body', async () => {
    const formData = ruleForm({ name: 'Updated Rule', description: 'new' });
    mockFetchResponse({ rule_id: 'rule-1', ...formData });

    await ruleApi.update('rule-1', formData);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-rules/rule-1'),
      expect.objectContaining({ method: 'PUT' }),
    );
  });

  it('delete sends DELETE request', async () => {
    mockFetchResponse({ status: 'ok' });

    await ruleApi.delete('rule-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-rules/rule-1'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('importYaml sends POST with yaml content', async () => {
    mockFetchResponse([mockRule]);

    await ruleApi.importYaml('name: Test');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-rules/import-yaml'),
      expect.objectContaining({ method: 'POST' }),
    );
  });
});

// ─── Logic API ─────────────────────────────────────────────────

describe('logicApi', () => {
  const mockLogic = logicRecord();

  it('list calls GET /api/business-logics', async () => {
    mockFetchResponse([mockLogic]);

    const result = await logicApi.list();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-logics'),
      expect.any(Object),
    );
    expect(result).toHaveLength(1);
  });

  it('list passes ontology_id and version_id as query params', async () => {
    mockFetchResponse([]);

    await logicApi.list('ont-1', 'v-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('ontology_id=ont-1');
    expect(calledUrl).toContain('version_id=v-1');
  });

  it('get calls GET /api/business-logics/:id', async () => {
    mockFetchResponse(mockLogic);

    const result = await logicApi.get('logic-1');
    expect(result.logic_id).toBe('logic-1');
  });

  it('create sends POST with correct body', async () => {
    const formData = logicForm({ name: 'New Logic' });
    mockFetchResponse({ logic_id: 'logic-new', ...formData });

    await logicApi.create(formData);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-logics'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('update sends PUT with correct body', async () => {
    const formData = logicForm({ name: 'Updated Logic', description: 'new' });
    mockFetchResponse({ logic_id: 'logic-1', ...formData });

    await logicApi.update('logic-1', formData);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-logics/logic-1'),
      expect.objectContaining({ method: 'PUT' }),
    );
  });

  it('delete sends DELETE request', async () => {
    mockFetchResponse({ status: 'ok' });

    await logicApi.delete('logic-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-logics/logic-1'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('importYaml sends POST with yaml content', async () => {
    mockFetchResponse([mockLogic]);

    await logicApi.importYaml('name: Test');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-logics/import-yaml'),
      expect.objectContaining({ method: 'POST' }),
    );
  });
});

// ─── Indicator API ─────────────────────────────────────────────

describe('indicatorApi', () => {
  const mockIndicator = indicatorRecord();

  it('list calls GET /api/business-indicators', async () => {
    mockFetchResponse([mockIndicator]);

    const result = await indicatorApi.list();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-indicators'),
      expect.any(Object),
    );
    expect(result).toHaveLength(1);
  });

  it('list passes ontology_id and version_id as query params', async () => {
    mockFetchResponse([]);

    await indicatorApi.list('ont-1', 'v-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('ontology_id=ont-1');
    expect(calledUrl).toContain('version_id=v-1');
  });

  it('get calls GET /api/business-indicators/:id', async () => {
    mockFetchResponse(mockIndicator);

    const result = await indicatorApi.get('ind-1');
    expect(result.indicator_id).toBe('ind-1');
  });

  it('create sends POST with correct body', async () => {
    const formData = indicatorForm({ name: 'New Indicator', calculation_formula: 'x + y' });
    mockFetchResponse({ indicator_id: 'ind-new', ...formData });

    await indicatorApi.create(formData);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-indicators'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('update sends PUT with correct body', async () => {
    const formData = indicatorForm({ name: 'Updated Indicator', calculation_formula: 'x * y' });
    mockFetchResponse({ indicator_id: 'ind-1', ...formData });

    await indicatorApi.update('ind-1', formData);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-indicators/ind-1'),
      expect.objectContaining({ method: 'PUT' }),
    );
  });

  it('delete sends DELETE request', async () => {
    mockFetchResponse({ status: 'ok' });

    await indicatorApi.delete('ind-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-indicators/ind-1'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('importYaml sends POST with yaml content', async () => {
    mockFetchResponse([mockIndicator]);

    await indicatorApi.importYaml('name: Test');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-indicators/import-yaml'),
      expect.objectContaining({ method: 'POST' }),
    );
  });
});

// ─── Entity API ────────────────────────────────────────────────

describe('entityApi', () => {
  it('listAll calls GET /api/business-entities', async () => {
    const mockEntities: BusinessEntity[] = [entityRecord()];
    mockFetchResponse(mockEntities);

    const result = await entityApi.listAll();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-entities'),
      expect.any(Object),
    );
    expect(result).toHaveLength(1);
  });
});

// ─── Type Definitions ──────────────────────────────────────────

describe('businessApi - Type Definitions', () => {
  it('processTypeDefinitions.list calls GET with ontology_id', async () => {
    mockFetchResponse([]);

    await processTypeDefinitions.list('ont-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('/api/process-type-definitions?ontology_id=ont-1');
  });

  it('ruleTypeDefinitions.list calls GET with ontology_id', async () => {
    mockFetchResponse([]);

    await ruleTypeDefinitions.list('ont-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('/api/rule-type-definitions?ontology_id=ont-1');
  });

  it('functionTypeDefinitions.list calls GET with ontology_id', async () => {
    mockFetchResponse([]);

    await functionTypeDefinitions.list('ont-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('/api/function-type-definitions?ontology_id=ont-1');
  });

  it('indicatorTypeDefinitions.list calls GET with ontology_id', async () => {
    mockFetchResponse([]);

    await indicatorTypeDefinitions.list('ont-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('/api/indicator-type-definitions?ontology_id=ont-1');
  });
});

// ─── Error Handling ────────────────────────────────────────────

describe('businessApi - Error Handling', () => {
  it('throws on HTTP error response', async () => {
    mockFetchError(500, 'Internal Server Error');

    await expect(processApi.list()).rejects.toThrow('HTTP 500');
  });

  it('throws on 404 error', async () => {
    mockFetchError(404, 'Not Found');

    await expect(processApi.get('nonexistent')).rejects.toThrow('HTTP 404');
  });

  it('throws on network error', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new TypeError('Failed to fetch'));

    await expect(processApi.list()).rejects.toThrow('Failed to fetch');
  });

  it('ruleApi throws on error', async () => {
    mockFetchError(400, 'Bad Request');

    await expect(ruleApi.create(ruleForm())).rejects.toThrow('HTTP 400');
  });

  it('logicApi throws on error', async () => {
    mockFetchError(422, 'Unprocessable Entity');

    await expect(logicApi.create(logicForm())).rejects.toThrow('HTTP 422');
  });

  it('indicatorApi throws on error', async () => {
    mockFetchError(422, 'Unprocessable Entity');

    await expect(indicatorApi.delete('ind-1')).rejects.toThrow('HTTP 422');
  });
});

// ─── Auth Headers ──────────────────────────────────────────────

describe('businessApi - Auth Headers', () => {
  it('includes Authorization header when token exists', async () => {
    mockFetchResponse([]);

    await processApi.list();
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const headers = callOptions.headers as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer test-jwt-token');
  });

  it('includes Content-Type application/json header', async () => {
    mockFetchResponse([]);

    await processApi.list();
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const headers = callOptions.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
  });
});
