import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useKnowledgeStore } from './knowledgeStore';

vi.mock('../services/knowledgePageApi', () => ({
  knowledgePageApi: {
    navigate: vi.fn(),
    getSynonyms: vi.fn(),
    addSynonym: vi.fn(),
    getExpansionRules: vi.fn(),
    addExpansionRule: vi.fn(),
    parseIntent: vi.fn(),
    planTasks: vi.fn(),
  },
}));

import { knowledgePageApi } from '../services/knowledgePageApi';

const mockNavigationResult = {
  navigation_id: 'nav-1',
  entity_id: 'entity-1',
  navigation_path: ['entity-1', 'entity-2'],
  related_entities: [{ id: 'entity-2', name: 'Related' }],
  entity_context: { type: 'object' },
};

describe('knowledgeStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useKnowledgeStore.setState({
      activeTab: 'navigation',
      navigationResults: null,
      synonyms: {},
      expansionRules: [],
      loading: false,
      error: null,
    });
  });

  describe('initial state', () => {
    it('has correct default values', () => {
      const state = useKnowledgeStore.getState();
      expect(state.activeTab).toBe('navigation');
      expect(state.navigationResults).toBeNull();
      expect(state.synonyms).toEqual({});
      expect(state.expansionRules).toEqual([]);
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('setActiveTab', () => {
    it('sets active tab', () => {
      useKnowledgeStore.getState().setActiveTab('synonyms');
      expect(useKnowledgeStore.getState().activeTab).toBe('synonyms');
    });
  });

  describe('navigate', () => {
    it('navigates to entity successfully', async () => {
      (knowledgePageApi.navigate as ReturnType<typeof vi.fn>).mockResolvedValue(mockNavigationResult);
      await useKnowledgeStore.getState().navigate('entity-1', 'outbound', 1);
      expect(knowledgePageApi.navigate).toHaveBeenCalledWith('entity-1', 'outbound', 1);
      expect(useKnowledgeStore.getState().navigationResults).toEqual(mockNavigationResult);
      expect(useKnowledgeStore.getState().loading).toBe(false);
    });

    it('uses default direction and depth', async () => {
      (knowledgePageApi.navigate as ReturnType<typeof vi.fn>).mockResolvedValue(mockNavigationResult);
      await useKnowledgeStore.getState().navigate('entity-1');
      expect(knowledgePageApi.navigate).toHaveBeenCalledWith('entity-1', 'outbound', 1);
    });

    it('handles navigate error', async () => {
      (knowledgePageApi.navigate as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Navigate failed'));
      await useKnowledgeStore.getState().navigate('bad-entity');
      expect(useKnowledgeStore.getState().error).toBe('Navigate failed');
      expect(useKnowledgeStore.getState().loading).toBe(false);
    });
  });

  describe('loadSynonyms', () => {
    it('loads synonyms successfully', async () => {
      (knowledgePageApi.getSynonyms as ReturnType<typeof vi.fn>).mockResolvedValue({
        synonyms: { entity: ['thing', 'object'] },
      });
      await useKnowledgeStore.getState().loadSynonyms();
      expect(useKnowledgeStore.getState().synonyms).toEqual({ entity: ['thing', 'object'] });
    });

    it('handles missing synonyms gracefully', async () => {
      (knowledgePageApi.getSynonyms as ReturnType<typeof vi.fn>).mockResolvedValue({});
      await useKnowledgeStore.getState().loadSynonyms();
      expect(useKnowledgeStore.getState().synonyms).toEqual({});
    });

    it('handles loadSynonyms error', async () => {
      (knowledgePageApi.getSynonyms as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Synonyms failed'));
      await useKnowledgeStore.getState().loadSynonyms();
      expect(useKnowledgeStore.getState().error).toBe('Synonyms failed');
    });
  });

  describe('addSynonym', () => {
    it('adds synonym and reloads list', async () => {
      (knowledgePageApi.addSynonym as ReturnType<typeof vi.fn>).mockResolvedValue({});
      (knowledgePageApi.getSynonyms as ReturnType<typeof vi.fn>).mockResolvedValue({
        synonyms: { entity: ['thing', 'object', 'item'] },
      });
      await useKnowledgeStore.getState().addSynonym('entity', 'item');
      expect(knowledgePageApi.addSynonym).toHaveBeenCalledWith('entity', 'item');
      expect(useKnowledgeStore.getState().synonyms).toEqual({ entity: ['thing', 'object', 'item'] });
    });

    it('handles addSynonym error', async () => {
      (knowledgePageApi.addSynonym as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Add synonym failed'));
      await useKnowledgeStore.getState().addSynonym('x', 'y');
      expect(useKnowledgeStore.getState().error).toBe('Add synonym failed');
    });
  });

  describe('loadExpansionRules', () => {
    it('loads expansion rules successfully', async () => {
      const rules = [{ pattern: 'test', expansion: ['a', 'b'] }];
      (knowledgePageApi.getExpansionRules as ReturnType<typeof vi.fn>).mockResolvedValue({ rules });
      await useKnowledgeStore.getState().loadExpansionRules();
      expect(useKnowledgeStore.getState().expansionRules).toEqual(rules);
    });

    it('handles missing rules gracefully', async () => {
      (knowledgePageApi.getExpansionRules as ReturnType<typeof vi.fn>).mockResolvedValue({});
      await useKnowledgeStore.getState().loadExpansionRules();
      expect(useKnowledgeStore.getState().expansionRules).toEqual([]);
    });

    it('handles loadExpansionRules error', async () => {
      (knowledgePageApi.getExpansionRules as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Rules failed'));
      await useKnowledgeStore.getState().loadExpansionRules();
      expect(useKnowledgeStore.getState().error).toBe('Rules failed');
    });
  });

  describe('addExpansionRule', () => {
    it('adds expansion rule and reloads list', async () => {
      const rules = [{ pattern: 'new', expansion: ['x', 'y'] }];
      (knowledgePageApi.addExpansionRule as ReturnType<typeof vi.fn>).mockResolvedValue({});
      (knowledgePageApi.getExpansionRules as ReturnType<typeof vi.fn>).mockResolvedValue({ rules });
      await useKnowledgeStore.getState().addExpansionRule('new', 'x,y');
      expect(knowledgePageApi.addExpansionRule).toHaveBeenCalledWith('new', 'x,y');
      expect(useKnowledgeStore.getState().expansionRules).toEqual(rules);
    });

    it('handles addExpansionRule error', async () => {
      (knowledgePageApi.addExpansionRule as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Add rule failed'));
      await useKnowledgeStore.getState().addExpansionRule('x', 'y');
      expect(useKnowledgeStore.getState().error).toBe('Add rule failed');
    });
  });

  describe('parseIntent', () => {
    it('parses intent successfully', async () => {
      const parsed = { intent: 'query', entities: ['e1'] };
      (knowledgePageApi.parseIntent as ReturnType<typeof vi.fn>).mockResolvedValue(parsed);
      const result = await useKnowledgeStore.getState().parseIntent('show me all entities');
      expect(result).toEqual(parsed);
      expect(useKnowledgeStore.getState().loading).toBe(false);
    });

    it('returns empty object on parse error', async () => {
      (knowledgePageApi.parseIntent as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Parse failed'));
      const result = await useKnowledgeStore.getState().parseIntent('bad input');
      expect(result).toEqual({});
      expect(useKnowledgeStore.getState().error).toBe('Parse failed');
    });
  });

  describe('planTasks', () => {
    it('plans tasks successfully', async () => {
      const plan = { tasks: [{ id: 't1', action: 'query' }] };
      (knowledgePageApi.planTasks as ReturnType<typeof vi.fn>).mockResolvedValue(plan);
      const result = await useKnowledgeStore.getState().planTasks('query entities', ['e1']);
      expect(result).toEqual(plan);
      expect(useKnowledgeStore.getState().loading).toBe(false);
    });

    it('returns empty object on plan error', async () => {
      (knowledgePageApi.planTasks as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Plan failed'));
      const result = await useKnowledgeStore.getState().planTasks('bad');
      expect(result).toEqual({});
      expect(useKnowledgeStore.getState().error).toBe('Plan failed');
    });

    it('uses default entities and filters', async () => {
      (knowledgePageApi.planTasks as ReturnType<typeof vi.fn>).mockResolvedValue({});
      await useKnowledgeStore.getState().planTasks('test');
      expect(knowledgePageApi.planTasks).toHaveBeenCalledWith('test', [], {});
    });
  });

  describe('clearError', () => {
    it('clears error state', () => {
      useKnowledgeStore.setState({ error: 'Some error' });
      useKnowledgeStore.getState().clearError();
      expect(useKnowledgeStore.getState().error).toBeNull();
    });
  });
});
