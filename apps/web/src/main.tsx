import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { I18nextProvider } from 'react-i18next';
// 1) Token 真源（镜像 docs/04-ui/design-tokens.css）必须最先引入：
//    它定义 primitive / semantic / component 三层变量与字体族。
import './modules/shared/styles/design-tokens.css';
// 2) 应用级基础样式（依赖上一步的 Token）
import './index.css';
// 3) 旧 Token 别名层 + Ant Design 6 覆盖
import './modules/shared/styles/global.css';
import i18n from './modules/shared/stores/i18nStore';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nextProvider i18n={i18n}>
      <App />
    </I18nextProvider>
  </StrictMode>,
);
