import { create } from 'zustand';
import { apiClient } from '@/modules/shared/services/apiClient';

interface Skill {
  name: string;
  category: string;
  path: string;
  files: string[];
  description?: string;
  parsed?: {
    name?: string;
    description?: string;
    input_schema?: Record<string, unknown>;
    output_schema?: Record<string, unknown>;
    sections?: Record<string, string>;
  };
  enabled?: boolean;
  skill_id?: string;
  type?: string;
  status?: string;
}

interface SkillState {
  skills: Skill[];
  currentSkill: Skill | null;
  loading: boolean;
  error: string | null;

  loadSkills: () => Promise<void>;
  registerSkill: (data: {
    name: string;
    skill_type: string;
    description?: string;
    category?: string;
  }) => Promise<void>;
  unregisterSkill: (name: string) => Promise<void>;
  discoverSkills: () => Promise<void>;
}

export const useSkillStore = create<SkillState>((set, get) => ({
  skills: [],
  currentSkill: null,
  loading: false,
  error: null,

  loadSkills: async () => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.get<{
        registered: Skill[];
        scanned: Skill[];
        total_registered: number;
        total_scanned: number;
      }>('/api/skills');
      set({ skills: data.registered || [], loading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load skills',
        loading: false,
      });
    }
  },

  registerSkill: async (data) => {
    set({ loading: true, error: null });
    try {
      await apiClient.post('/api/skills/register', data);
      await get().loadSkills();
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to register skill',
        loading: false,
      });
    }
  },

  unregisterSkill: async (name) => {
    set({ loading: true, error: null });
    try {
      await apiClient.delete(`/api/skills/${encodeURIComponent(name)}`);
      await get().loadSkills();
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to unregister skill',
        loading: false,
      });
    }
  },

  discoverSkills: async () => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.get<{
        skills: Skill[];
        total: number;
      }>('/api/skills/scan');
      set({ skills: data.skills || [], loading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to discover skills',
        loading: false,
      });
    }
  },
}));
