import { OpenHarnessProvider } from '@openharness/react';

const API_ENDPOINT = (import.meta.env.VITE_API_BASE || '') + '/api/qa';

export interface QAIProviderProps {
  children: React.ReactNode;
}

export function QAIProvider({ children }: QAIProviderProps) {
  return (
    <OpenHarnessProvider>
      {children}
    </OpenHarnessProvider>
  );
}

export { API_ENDPOINT };
