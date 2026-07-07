import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const proxyTarget = process.env.PROXY_TARGET || process.env.VITE_API_BASE || 'http://localhost:8000';
console.log('[vite config] PROXY_TARGET env:', process.env.PROXY_TARGET);
console.log('[vite config] VITE_API_BASE env:', process.env.VITE_API_BASE);
console.log('[vite config] Resolved proxy target:', proxyTarget);

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  optimizeDeps: {
    include: ['jit-viewer'],
  },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    hmr: {
      clientPort: 5173,
      host: 'localhost',
      protocol: 'ws',
    },
    watch: {
      usePolling: true,
      interval: 1000,
    },
    headers: {
      'Cache-Control': 'no-store',
    },
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            console.log('[proxy error]', err.message);
          });
          proxy.on('proxyReq', (_proxyReq, req) => {
            console.log('[proxy req]', req.method, req.url, '→', proxyTarget + req.url);
          });
          proxy.on('proxyRes', (proxyRes, req) => {
            console.log('[proxy res]', proxyRes.statusCode, req.url);
          });
        },
      },
      '/ws': {
        target: proxyTarget.replace(/^http/, 'ws'),
        ws: true,
        changeOrigin: true,
      },
      '/health': {
        target: proxyTarget,
        changeOrigin: true,
      },
      '/uploads': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
})
