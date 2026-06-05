import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import './modules/shared/styles/global.css';
import './modules/shared/stores/i18nStore';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);