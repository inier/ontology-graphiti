import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import { fetchJson } from '../services/apiClient';
import { API_BASE } from '@/config';
import type { LocaleInfo } from '@/modules/i18n-admin/services/i18nApi';

// Shared
import commonZh from '../locales/zh-CN/common.json';
import commonEn from '../locales/en-US/common.json';
import messagesZh from '../locales/zh-CN/messages.json';
import messagesEn from '../locales/en-US/messages.json';

// Agent
import agentZh from '@/modules/agent/locales/zh-CN/agent.json';
import agentEn from '@/modules/agent/locales/en-US/agent.json';

// Audit
import auditZh from '@/modules/audit/locales/zh-CN/audit.json';
import auditEn from '@/modules/audit/locales/en-US/audit.json';

// Ontology
import ontologyZh from '@/modules/ontology/locales/zh-CN/ontology.json';
import ontologyEn from '@/modules/ontology/locales/en-US/ontology.json';

// Simulation
import simulationZh from '@/modules/simulation/locales/zh-CN/simulation.json';
import simulationEn from '@/modules/simulation/locales/en-US/simulation.json';

// Workspace
import workspaceZh from '@/modules/workspace/locales/zh-CN/workspace.json';
import workspaceEn from '@/modules/workspace/locales/en-US/workspace.json';

// QA
import qaZh from '@/modules/qa/locales/zh-CN/qa.json';
import qaEn from '@/modules/qa/locales/en-US/qa.json';

// Knowledge
import knowledgeZh from '@/modules/knowledge/locales/zh-CN/knowledge.json';
import knowledgeEn from '@/modules/knowledge/locales/en-US/knowledge.json';

// System
import systemZh from '@/modules/system/locales/zh-CN/system.json';
import systemEn from '@/modules/system/locales/en-US/system.json';

// menu-config
import menuConfigZh from '@/modules/menu-config/locales/zh-CN/menu-config.json';
import menuConfigEn from '@/modules/menu-config/locales/en-US/menu-config.json';
import menuNamesZh from '@/modules/menu-config/locales/zh-CN/menu-names.json';
import menuNamesEn from '@/modules/menu-config/locales/en-US/menu-names.json';

// i18n-admin
import i18nAdminZh from '@/modules/i18n-admin/locales/zh-CN/i18n-admin.json';
import i18nAdminEn from '@/modules/i18n-admin/locales/en-US/i18n-admin.json';

// settings
import settingsZh from '@/modules/settings/locales/zh-CN/settings.json';
import settingsEn from '@/modules/settings/locales/en-US/settings.json';

// business
import businessZh from '@/modules/business/locales/zh-CN/business.json';
import businessEn from '@/modules/business/locales/en-US/business.json';

// config
import configZh from '@/modules/config/locales/zh-CN/config.json';
import configEn from '@/modules/config/locales/en-US/config.json';

// guide
import guideZh from '@/modules/guide/locales/zh-CN/guide.json';
import guideEn from '@/modules/guide/locales/en-US/guide.json';

// ingest
import ingestZh from '@/modules/ingest/locales/zh-CN/ingest.json';
import ingestEn from '@/modules/ingest/locales/en-US/ingest.json';

// roles
import rolesZh from '@/modules/roles/locales/zh-CN/roles.json';
import rolesEn from '@/modules/roles/locales/en-US/roles.json';

// version
import versionZh from '@/modules/version/locales/zh-CN/version.json';
import versionEn from '@/modules/version/locales/en-US/version.json';

// ai-assistant
import aiAssistantZh from '@/modules/ai-assistant/locales/zh-CN/ai-assistant.json';
import aiAssistantEn from '@/modules/ai-assistant/locales/en-US/ai-assistant.json';

const STORAGE_KEY = 'odap-locale';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      'zh-CN': {
        common: commonZh,
        messages: messagesZh,
        agent: agentZh,
        audit: auditZh,
        ontology: ontologyZh,
        simulation: simulationZh,
        workspace: workspaceZh,
        qa: qaZh,
        knowledge: knowledgeZh,
        system: systemZh,
        'menu-config': menuConfigZh,
        'menu-names': menuNamesZh,
        'i18n-admin': i18nAdminZh,
        settings: settingsZh,
        business: businessZh,
        config: configZh,
        guide: guideZh,
        ingest: ingestZh,
        roles: rolesZh,
        version: versionZh,
        'ai-assistant': aiAssistantZh,
      },
      'en-US': {
        common: commonEn,
        messages: messagesEn,
        agent: agentEn,
        audit: auditEn,
        ontology: ontologyEn,
        simulation: simulationEn,
        workspace: workspaceEn,
        qa: qaEn,
        knowledge: knowledgeEn,
        system: systemEn,
        'menu-config': menuConfigEn,
        'menu-names': menuNamesEn,
        'i18n-admin': i18nAdminEn,
        settings: settingsEn,
        business: businessEn,
        config: configEn,
        guide: guideEn,
        ingest: ingestEn,
        roles: rolesEn,
        version: versionEn,
        'ai-assistant': aiAssistantEn,
      },
    },
    fallbackLng: 'zh-CN',
    ns: ['common', 'messages', 'agent', 'audit', 'ontology', 'simulation', 'workspace', 'qa', 'knowledge', 'system', 'menu-config', 'menu-names', 'i18n-admin', 'settings', 'business', 'config', 'guide', 'ingest', 'roles', 'version', 'ai-assistant'],
    defaultNS: 'common',
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: STORAGE_KEY,
      caches: ['localStorage'],
    },
  });

export default i18n;

export type Locale = 'zh-CN' | 'en-US';

export function setLocale(locale: Locale): void {
  i18n.changeLanguage(locale);
}

export function getCurrentLocale(): Locale {
  return (i18n.language as Locale) || 'zh-CN';
}

// ---------------------------------------------------------------------------
// 后端语言列表缓存
// ---------------------------------------------------------------------------

let cachedLocales: LocaleInfo[] = [];
let bootstrapPromise: Promise<LocaleInfo[]> | null = null;

/**
 * 从后端 /api/i18n/locales 拉取可用语言列表并缓存。
 *
 * - 幂等：并发/重复调用只发一次请求
 * - 容错：后端不可用时返回空数组，不抛异常
 */
export async function bootstrapI18n(): Promise<LocaleInfo[]> {
  if (bootstrapPromise) return bootstrapPromise;

  bootstrapPromise = (async () => {
    try {
      const data = await fetchJson<{ locales: LocaleInfo[]; count: number }>(
        `${API_BASE}/api/i18n/locales`,
      );
      cachedLocales = (data?.locales ?? []).filter((l) => l.is_active);
    } catch (e) {
      console.warn('bootstrapI18n: failed to fetch locales', e);
      cachedLocales = [];
    }
    return cachedLocales;
  })();

  try {
    return await bootstrapPromise;
  } finally {
    bootstrapPromise = null;
  }
}

/**
 * 返回 bootstrapI18n() 缓存的语言列表（同步）。
 * 若尚未 bootstrap，返回空数组。
 */
export function getCachedLocales(): LocaleInfo[] {
  return cachedLocales;
}
