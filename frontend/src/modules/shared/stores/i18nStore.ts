import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

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
      },
    },
    fallbackLng: 'zh-CN',
    ns: ['common', 'messages', 'agent', 'audit', 'ontology', 'simulation', 'workspace', 'qa', 'knowledge', 'system'],
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
