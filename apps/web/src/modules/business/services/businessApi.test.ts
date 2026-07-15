import { describe, it, expect, vi, beforeEach } from 'vitest';
import { processApi, ruleApi, logicApi, indicatorApi, entityApi, processTypeDefinitions, ruleTypeDefinitions, functionTypeDefinitions, indicatorTypeDefinitions } from './businessApi';

const API_BASE = 'http://localhost:8000';

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
  const mockProcess = {
    id: 'proc-1',
    name: 'Order Process',
    description: 'desc',
    steps: [],
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  };

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
    expect(result.id).toBe('proc-1');
  });

  it('create sends POST with correct body', async () => {
    const formData = { name: 'New Process', description: 'desc', steps: [] };
    mockFetchResponse({ id: 'proc-new', ...formData });

    const result = await processApi.create(formData as any);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-processes'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(formData),
      }),
    );
  });

  it('create passes ontology_id and version_id in body', async () => {
    const formData = { name: 'New', ontology_id: 'ont-1', version_id: 'v-1' };
    mockFetchResponse({ id: 'proc-new', ...formData });

    await processApi.create(formData as any);
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    expect(JSON.parse(callOptions.body as string)).toEqual(formData);
  });

  it('update sends PUT with correct body', async () => {
    const formData = { name: 'Updated Process', description: 'new desc', steps: [] };
    mockFetchResponse({ id: 'proc-1', ...formData });

    await processApi.update('proc-1', formData as any);
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
  const mockRule = {
    id: 'rule-1',
    name: 'Validation Rule',
    description: 'desc',
    conditions: [],
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  };

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
    expect(result.id).toBe('rule-1');
  });

  it('create sends POST with correct body', async () => {
    const formData = { name: 'New Rule', description: 'desc', conditions: [] };
    mockFetchResponse({ id: 'rule-new', ...formData });

    await ruleApi.create(formData as any);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-rules'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('update sends PUT with correct body', async () => {
    const formData = { name: 'Updated Rule', description: 'new', conditions: [] };
    mockFetchResponse({ id: 'rule-1', ...formData });

    await ruleApi.update('rule-1', formData as any);
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
  const mockLogic = {
    id: 'logic-1',
    name: 'Calculation Logic',
    description: 'desc',
    expressions: [],
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  };

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
    expect(result.id).toBe('logic-1');
  });

  it('create sends POST with correct body', async () => {
    const formData = { name: 'New Logic', description: 'desc', expressions: [] };
    mockFetchResponse({ id: 'logic-new', ...formData });

    await logicApi.create(formData as any);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-logics'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('update sends PUT with correct body', async () => {
    const formData = { name: 'Updated Logic', description: 'new', expressions: [] };
    mockFetchResponse({ id: 'logic-1', ...formData });

    await logicApi.update('logic-1', formData as any);
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
  const mockIndicator = {
    id: 'ind-1',
    name: 'Revenue Indicator',
    description: 'desc',
    formula: '',
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  };

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
    expect(result.id).toBe('ind-1');
  });

  it('create sends POST with correct body', async () => {
    const formData = { name: 'New Indicator', description: 'desc', formula: 'x + y' };
    mockFetchResponse({ id: 'ind-new', ...formData });

    await indicatorApi.create(formData as any);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/business-indicators'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('update sends PUT with correct body', async () => {
    const formData = { name: 'Updated Indicator', description: 'new', formula: 'x * y' };
    mockFetchResponse({ id: 'ind-1', ...formData });

    await indicatorApi.update('ind-1', formData as any);
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
    const mockEntities = [{ id: 'ent-1', name: 'Customer' }];
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

    await expect(ruleApi.create({} as any)).rejects.toThrow('HTTP 400');
  });

  it('logicApi throws on error', async () => {
    mockFetchError(422, 'Unprocessable Entity');

    await expect(logicApi.create({} as any)).rejects.toThrow('HTTP 422');
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
