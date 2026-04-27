import { OpenHarnessProvider } from '@openharness/react';

const API_ENDPOINT = 'http://localhost:8000/api/qa';

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
