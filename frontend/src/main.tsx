import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { AppLayout } from './components/AppLayout';
import { AppRoutes } from './AppRoutes';
import './styles/global.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ConfigProvider locale={zhCN}>
        <AppLayout>
          <AppRoutes />
        </AppLayout>
      </ConfigProvider>
    </BrowserRouter>
  </StrictMode>
);
