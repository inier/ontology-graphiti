import { create } from 'zustand';
import { apiClient } from '@/modules/shared/services/apiClient';

interface IntentResult {
  intent_id?: string;
  primary_intent?: string;
  confidence: number;
  entities: string[];
  attributes: Record<string, unknown>;
  alternative_intents: string[];
}

interface NavigationResult {
  navigation_id?: string;
  entity_id: string;
  navigation_path: string[];
  related_entities: Record<string, unknown>[];
  entity_context: Record<string, unknown>;
}

interface ExplanationResult {
  explanation_id?: string;
  decision_id: string;
  query: string;
  answer: string;
  confidence: number;
  reasoning_chain: Record<string, unknown>[];
  sources: string[];
}

type RoleView = 'director' | 'intelligence' | 'operations';

interface CognitionState {
  intentResult: IntentResult | null;
  navigationPath: NavigationResult | null;
  explanation: ExplanationResult | null;
  roleView: RoleView;
  loading: boolean;
  error: string | null;

  recognizeIntent: (inputText: string, role?: string) => Promise<void>;
  navigate: (entityId: string, direction?: string) => Promise<void>;
  explain: (decisionId: string, context?: Record<string, unknown>) => Promise<void>;
  switchRoleView: (role: RoleView) => void;
  clearError: () => void;
}

export const useCognitionStore = create<CognitionState>((set) => ({
  intentResult: null,
  navigationPath: null,
  explanation: null,
  roleView: 'director',
  loading: false,
  error: null,

  recognizeIntent: async (inputText, role) => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.post<IntentResult>('/api/cognition/recognize-intent', {
        input_text: inputText,
        role: role || 'guest',
      });
      set({ intentResult: data, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  navigate: async (entityId, direction) => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.post<NavigationResult>('/api/cognition/navigate', {
        entity_id: entityId,
        direction: direction || 'outbound',
      });
      set({ navigationPath: data, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  explain: async (decisionId, context) => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.post<ExplanationResult>('/api/cognition/explain', {
        decision_id: decisionId,
        context: context || {},
      });
      set({ explanation: data, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  switchRoleView: (role) => {
    set({ roleView: role });
  },

  clearError: () => set({ error: null }),
}));
