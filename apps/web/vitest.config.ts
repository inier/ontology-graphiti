/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // P4-2: Vitest 4 + Vite 8 对 CJS/ESM 互操作更严格。
    // @ant-design/pro-components 的 lib/*.js 使用 CJS exports 语法，
    // 但其 package.json 声明 "type": "module"，导致 ReferenceError: exports is not defined。
    // 通过 server.deps.inline 强制 Vitest 转换这些 CJS 依赖。
    server: {
      deps: {
        inline: ['@ant-design/pro-components'],
      },
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      // P1 验收硬门槛：semantic-admin 模块整体覆盖率不得低于 70%；低于此阈值 CI 直接 FAIL。
      thresholds: {
        lines: 70,
        functions: 70,
        branches: 70,
        statements: 70,
        'src/modules/semantic-admin/**': {
          lines: 70,
          functions: 70,
          branches: 70,
          statements: 70,
        },
      },
    },
  },
})
