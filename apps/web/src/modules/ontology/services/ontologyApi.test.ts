import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ontologyApi } from './ontologyApi';
import type { EntityType, OntologyDocument, InstanceData } from './ontologyApi';

const API_BASE = 'http://localhost:8000';
const BASE = `${API_BASE}/api/ontology/model`;

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

// ─── Entity Type CRUD ──────────────────────────────────────────

describe('ontologyApi - Entity Type CRUD', () => {
  const mockEntityType: EntityType = {
    type_id: 'type-1',
    name: 'Person',
    display_name: 'Person',
    description: 'A person entity',
    classification_level: 'U',
    properties: [],
    relations: [],
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  };

  it('listEntityTypes calls correct endpoint', async () => {
    mockFetchResponse([mockEntityType]);

    const result = await ontologyApi.listEntityTypes('doc-1');
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/doc-1/entity-types`,
      expect.any(Object),
    );
    expect(result).toHaveLength(1);
    expect(result[0].type_id).toBe('type-1');
  });

  it('getEntityType calls correct endpoint', async () => {
    mockFetchResponse(mockEntityType);

    const result = await ontologyApi.getEntityType('doc-1', 'type-1');
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/doc-1/entity-types/type-1`,
      expect.any(Object),
    );
    expect(result.name).toBe('Person');
  });

  it('createEntityType sends POST with correct body', async () => {
    const createData = {
      name: 'Person',
      display_name: 'Person',
      description: 'A person',
      classification_level: 'U' as const,
      properties: [],
      relations: [],
    };
    mockFetchResponse(mockEntityType);

    const result = await ontologyApi.createEntityType('doc-1', createData);
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/doc-1/entity-types`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(createData),
      }),
    );
    expect(result.type_id).toBe('type-1');
  });

  it('updateEntityType sends PUT with correct body', async () => {
    const updateData = { description: 'Updated description' };
    mockFetchResponse({ ...mockEntityType, description: 'Updated description' });

    const result = await ontologyApi.updateEntityType('doc-1', 'type-1', updateData);
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/doc-1/entity-types/type-1`,
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(updateData),
      }),
    );
    expect(result.description).toBe('Updated description');
  });

  it('deleteEntityType sends DELETE request', async () => {
    mockFetchResponse(undefined);

    await ontologyApi.deleteEntityType('doc-1', 'type-1');
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/doc-1/entity-types/type-1`,
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});

// ─── Instance CRUD ─────────────────────────────────────────────

describe('ontologyApi - Instance CRUD', () => {
  const mockInstance: InstanceData = {
    instance_id: 'inst-1',
    type_id: 'type-1',
    type_name: 'Person',
    properties: { name: 'Alice' },
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  };

  it('listInstances calls correct endpoint with pagination', async () => {
    mockFetchResponse({ instances: [mockInstance], total: 1 });

    const result = await ontologyApi.listInstances('doc-1', 'type-1', 1, 10);
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('/entity-types/type-1/instances?');
    expect(calledUrl).toContain('page=1');
    expect(calledUrl).toContain('page_size=10');
    expect(result.instances).toHaveLength(1);
    expect(result.total).toBe(1);
  });

  it('listInstances works without pagination params', async () => {
    mockFetchResponse({ instances: [], total: 0 });

    const result = await ontologyApi.listInstances('doc-1', 'type-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).not.toContain('?');
    expect(result.instances).toHaveLength(0);
  });

  it('createInstance sends POST with correct body', async () => {
    const data = { name: 'Bob' };
    mockFetchResponse(mockInstance);

    const result = await ontologyApi.createInstance('doc-1', 'type-1', data);
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/doc-1/entity-types/type-1/instances`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(data),
      }),
    );
    expect(result.instance_id).toBe('inst-1');
  });

  it('updateInstance sends PUT with correct body', async () => {
    const data = { name: 'Charlie' };
    mockFetchResponse({ ...mockInstance, properties: { name: 'Charlie' } });

    const result = await ontologyApi.updateInstance('doc-1', 'type-1', 'inst-1', data);
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/doc-1/entity-types/type-1/instances/inst-1`,
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    );
  });

  it('deleteInstance sends DELETE request', async () => {
    mockFetchResponse(undefined);

    await ontologyApi.deleteInstance('doc-1', 'type-1', 'inst-1');
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/doc-1/entity-types/type-1/instances/inst-1`,
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('batchImport sends POST with instances array', async () => {
    const instances = [{ name: 'A' }, { name: 'B' }];
    mockFetchResponse({ imported_count: 2 });

    const result = await ontologyApi.batchImport('doc-1', 'type-1', instances);
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/doc-1/entity-types/type-1/instances/batch`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ instances }),
      }),
    );
    expect(result.imported_count).toBe(2);
  });
});

// ─── Document Operations ───────────────────────────────────────

describe('ontologyApi - Document Operations', () => {
  it('loadOntologyDocument calls correct endpoint', async () => {
    const mockDoc: OntologyDocument = {
      document_id: 'doc-1',
      name: 'Test Ontology',
      description: 'desc',
      version: '1.0',
      entity_types: [],
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    };
    mockFetchResponse(mockDoc);

    const result = await ontologyApi.loadOntologyDocument('doc-1');
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/doc-1`,
      expect.any(Object),
    );
    expect(result.document_id).toBe('doc-1');
  });

  it('exportDocument calls endpoint with format param', async () => {
    mockFetchResponse({ format: 'json', data: {} });

    const result = await ontologyApi.exportDocument('doc-1', 'yaml');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('/doc-1/export?format=yaml');
    expect(result.format).toBe('json');
  });

  it('exportDocument defaults to json format', async () => {
    mockFetchResponse({ format: 'json', data: {} });

    await ontologyApi.exportDocument('doc-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('format=json');
  });
});

// ─── Ontology CRUD (via apiClient) ─────────────────────────────

describe('ontologyApi.ontologies - CRUD', () => {
  it('list calls GET /api/ontologies', async () => {
    mockFetchResponse([]);

    const result = await ontologyApi.ontologies.list();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ontologies'),
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('list passes workspace_id as query param', async () => {
    mockFetchResponse([]);

    await ontologyApi.ontologies.list('ws-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('workspace_id=ws-1');
  });

  it('get calls GET /api/ontologies/:id', async () => {
    mockFetchResponse({ id: 'ont-1', name: 'Test' });

    await ontologyApi.ontologies.get('ont-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ontologies/ont-1'),
      expect.any(Object),
    );
  });

  it('create sends POST to /api/ontologies', async () => {
    const data = { name: 'New Ontology', workspace_id: 'ws-1' };
    mockFetchResponse({ id: 'ont-new', ...data });

    await ontologyApi.ontologies.create(data);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ontologies'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('update sends PUT to /api/ontologies/:id', async () => {
    mockFetchResponse({ id: 'ont-1', name: 'Updated' });

    await ontologyApi.ontologies.update('ont-1', { name: 'Updated' });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ontologies/ont-1'),
      expect.objectContaining({ method: 'PUT' }),
    );
  });

  it('delete sends DELETE to /api/ontologies/:id', async () => {
    mockFetchResponse({ status: 'ok' });

    await ontologyApi.ontologies.delete('ont-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ontologies/ont-1'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});

// ─── Schema Versions ───────────────────────────────────────────

describe('ontologyApi.schemaVersions', () => {
  it('list calls GET /api/ontologies/:id/versions', async () => {
    mockFetchResponse([]);

    await ontologyApi.schemaVersions.list('ont-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ontologies/ont-1/versions'),
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('commit sends POST with changelog', async () => {
    mockFetchResponse({ version_id: 'v2' });

    await ontologyApi.schemaVersions.commit('ont-1', 'Initial commit');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ontologies/ont-1/commit'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ changelog: 'Initial commit' }),
      }),
    );
  });

  it('diff calls GET with version_id_a and version_id_b', async () => {
    mockFetchResponse({});

    await ontologyApi.schemaVersions.diff('ont-1', 'v1', 'v2');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('version_id_a=v1');
    expect(calledUrl).toContain('version_id_b=v2');
  });

  it('rollback sends POST with target_version_id', async () => {
    mockFetchResponse({ status: 'ok' });

    await ontologyApi.schemaVersions.rollback('ont-1', 'v1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ontologies/ont-1/rollback'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_version_id: 'v1' }),
      }),
    );
  });
});

// ─── Type Definitions (Object, Link, Action, Process, Rule, Function, Indicator) ──

describe('ontologyApi - Type Definitions', () => {
  const typeGroups = [
    { name: 'objectTypeDefinitions', path: 'object-types' },
    { name: 'linkTypeDefinitions', path: 'link-types' },
    { name: 'actionTypeDefinitions', path: 'action-types' },
    { name: 'processTypeDefinitions', path: 'process-types' },
    { name: 'ruleTypeDefinitions', path: 'rule-types' },
    { name: 'functionTypeDefinitions', path: 'function-types' },
    { name: 'indicatorTypeDefinitions', path: 'indicator-types' },
  ] as const;

  typeGroups.forEach(({ name, path }) => {
    describe(`ontologyApi.${name}`, () => {
      it('list calls GET with ontology_id', async () => {
        mockFetchResponse([]);

        await ontologyApi[name].list('ont-1');
        expect(fetch).toHaveBeenCalledWith(
          expect.stringContaining(`/api/ontologies/ont-1/${path}`),
          expect.objectContaining({ method: 'GET' }),
        );
      });

      it('create sends POST', async () => {
        mockFetchResponse({ id: 'new' });

        await ontologyApi[name].create('ont-1', { name: 'Test' });
        expect(fetch).toHaveBeenCalledWith(
          expect.stringContaining(`/api/ontologies/ont-1/${path}`),
          expect.objectContaining({ method: 'POST' }),
        );
      });

      it('delete sends DELETE', async () => {
        mockFetchResponse({ status: 'ok' });

        await ontologyApi[name].delete('ont-1', 'type-1');
        expect(fetch).toHaveBeenCalledWith(
          expect.stringContaining(`/api/ontologies/${path}/type-1`),
          expect.objectContaining({ method: 'DELETE' }),
        );
      });
    });
  });
});

// ─── Graph ─────────────────────────────────────────────────────

describe('ontologyApi.graph', () => {
  it('get calls GET /api/ontologies/:id/graph', async () => {
    mockFetchResponse({ nodes: [], edges: [] });

    await ontologyApi.graph.get('ont-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ontologies/ont-1/graph'),
      expect.objectContaining({ method: 'GET' }),
    );
  });
});

// ─── Database Connections ──────────────────────────────────────

describe('ontologyApi.databaseConnections', () => {
  it('list calls GET with workspace_id', async () => {
    mockFetchResponse([]);

    await ontologyApi.databaseConnections.list('ws-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('/api/ontologies/database-connections?');
    expect(calledUrl).toContain('workspace_id=ws-1');
  });

  it('save sends POST', async () => {
    mockFetchResponse({ id: 'conn-1' });

    await ontologyApi.databaseConnections.save({ name: 'MyDB' });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ontologies/database-connections'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('delete sends DELETE', async () => {
    mockFetchResponse({ status: 'ok' });

    await ontologyApi.databaseConnections.delete('conn-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ontologies/database-connections/conn-1'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});

// ─── Extraction ────────────────────────────────────────────────

describe('ontologyApi.extraction', () => {
  it('testConnection sends POST', async () => {
    mockFetchResponse({ success: true });

    await ontologyApi.extraction.testConnection({ host: 'localhost' });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/extraction/test-connection'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('extractDatabase sends POST', async () => {
    mockFetchResponse({ session_id: 'sess-1' });

    await ontologyApi.extraction.extractDatabase({ connection_id: 'conn-1' });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/extraction/extract/database'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('extractNL sends POST', async () => {
    mockFetchResponse({ session_id: 'sess-2' });

    await ontologyApi.extraction.extractNL({ text: 'some text' });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/extraction/extract/natural-language'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('getSession calls GET', async () => {
    mockFetchResponse({ session_id: 'sess-1', status: 'completed' });

    await ontologyApi.extraction.getSession('sess-1');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/extraction/sessions/sess-1'),
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('confirm sends POST with data', async () => {
    mockFetchResponse({ status: 'confirmed' });

    await ontologyApi.extraction.confirm('sess-1', { approved: true });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/extraction/sessions/sess-1/confirm'),
      expect.objectContaining({ method: 'POST' }),
    );
  });
});

// ─── Error Handling ────────────────────────────────────────────

describe('ontologyApi - Error Handling', () => {
  it('throws on HTTP error response', async () => {
    mockFetchError(500, 'Internal Server Error');

    await expect(ontologyApi.listEntityTypes('doc-1')).rejects.toThrow('HTTP 500');
  });

  it('throws on 404 error', async () => {
    mockFetchError(404, 'Not Found');

    await expect(ontologyApi.getEntityType('doc-1', 'nonexistent')).rejects.toThrow('HTTP 404');
  });

  it('throws on network error', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new TypeError('Failed to fetch'));

    await expect(ontologyApi.listEntityTypes('doc-1')).rejects.toThrow('Failed to fetch');
  });
});

// ─── Auth Headers ──────────────────────────────────────────────

describe('ontologyApi - Auth Headers', () => {
  it('includes Authorization header when token exists', async () => {
    mockFetchResponse([]);

    await ontologyApi.listEntityTypes('doc-1');
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const headers = callOptions.headers as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer test-jwt-token');
  });

  it('includes Content-Type application/json header', async () => {
    mockFetchResponse([]);

    await ontologyApi.listEntityTypes('doc-1');
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const headers = callOptions.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
  });
});
