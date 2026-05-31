import { create } from 'zustand';
import { knowledgePageApi } from '../services/knowledgePageApi';

interface NavigationResult {
  navigation_id: string;
  entity_id: string;
  navigation_path: string[];
  related_entities: Record<string, unknown>[];
  entity_context: Record<string, unknown>;
}

interface SynonymMap {
  [canonical: string]: string[];
}

interface ExpansionRule {
  pattern: string;
  expansion: string[];
}

interface KnowledgeState {
  activeTab: string;
  navigationResults: NavigationResult | null;
  synonyms: SynonymMap;
  expansionRules: ExpansionRule[];
  loading: boolean;
  error: string | null;

  setActiveTab: (tab: string) => void;
  navigate: (entityId: string, direction?: string, depth?: number) => Promise<void>;
  loadSynonyms: () => Promise<void>;
  addSynonym: (canonical: string, synonym: string) => Promise<void>;
  loadExpansionRules: () => Promise<void>;
  addExpansionRule: (pattern: string, expansion: string) => Promise<void>;
  parseIntent: (text: string) => Promise<Record<string, unknown>>;
  planTasks: (intent: string, entities?: string[], filters?: Record<string, unknown>) => Promise<Record<string, unknown>>;
  clearError: () => void;
}

export const useKnowledgeStore = create<KnowledgeState>((set, get) => ({
  activeTab: 'navigation',
  navigationResults: null,
  synonyms: {},
  expansionRules: [],
  loading: false,
  error: null,

  setActiveTab: (tab) => set({ activeTab: tab }),

  navigate: async (entityId, direction = 'outbound', depth = 1) => {
    set({ loading: true, error: null });
    try {
      const results = await knowledgePageApi.navigate(entityId, direction, depth);
      set({ navigationResults: results, loading: false });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  loadSynonyms: async () => {
    try {
      const data = await knowledgePageApi.getSynonyms();
      set({ synonyms: data.synonyms || {} });
    } catch (e: unknown) {
      set({ error: (e as Error).message });
    }
  },

  addSynonym: async (canonical, synonym) => {
    try {
      await knowledgePageApi.addSynonym(canonical, synonym);
      const data = await knowledgePageApi.getSynonyms();
      set({ synonyms: data.synonyms || {} });
    } catch (e: unknown) {
      set({ error: (e as Error).message });
    }
  },

  loadExpansionRules: async () => {
    try {
      const data = await knowledgePageApi.getExpansionRules();
      set({ expansionRules: data.rules || [] });
    } catch (e: unknown) {
      set({ error: (e as Error).message });
    }
  },

  addExpansionRule: async (pattern, expansion) => {
    try {
      await knowledgePageApi.addExpansionRule(pattern, expansion);
      const data = await knowledgePageApi.getExpansionRules();
      set({ expansionRules: data.rules || [] });
    } catch (e: unknown) {
      set({ error: (e as Error).message });
    }
  },

  parseIntent: async (text) => {
    set({ loading: true, error: null });
    try {
      const result = await knowledgePageApi.parseIntent(text);
      set({ loading: false });
      return result;
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
      return {};
    }
  },

  planTasks: async (intent, entities = [], filters = {}) => {
    set({ loading: true, error: null });
    try {
      const result = await knowledgePageApi.planTasks(intent, entities, filters);
      set({ loading: false });
      return result;
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
      return {};
    }
  },

  clearError: () => set({ error: null }),
}));
