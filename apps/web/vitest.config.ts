/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  // 强制 esbuild 对所有 .tsx 文件使用 automatic JSX runtime，
  // 这样测试文件无需 `import React from 'react'` 即可使用 JSX。
  // 不加此项时，部分测试文件（StatCard/PageHeader/GraphControls/GraphToolbar）
  // 会报 `React is not defined`——esbuild 默认用 classic runtime (React.createElement)。
  esbuild: {
    jsx: 'automatic',
  },
  resolve: {
    alias: [
      { find: '@', replacement: path.resolve(__dirname, './src') },
      // 精确匹配顶层包，强制走 es/index.js（ESM）。
      // pro-components package.json 声明 type:module 但 main 指向 lib/index.js（CJS），
      // vite 在 jsdom 环境选了 main 而非 module，导致顶层 import 触发 lib/index.js 的 require() 报错。
      // 注意：pnpm workspace 下 node_modules 在 workspace 根（/app），apps/web 无本地 node_modules，
      // 故用 ../../node_modules 回退到根。host 侧若直接跑 vitest，__dirname 即 apps/web，
      // ../../node_modules 同样指向 monorepo 根。
      { find: /^@ant-design\/pro-components$/, replacement: path.resolve(__dirname, '../../node_modules/@ant-design/pro-components/es/index.js') },
      // lib/ 子路径也重定向到 es/（防御性，处理包内深 import）
      { find: '@ant-design/pro-components/lib', replacement: '@ant-design/pro-components/es' },
    ],
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // P4-2: Vitest 4 + Vite 8 对 CJS/ESM 互操作更严格。
    // @ant-design/pro-components 的 lib/*.js 使用 CJS require() 语法，
    // 但其 package.json 声明 "type": "module"，导致 "require is not defined in ES module scope"。
    // 三重处理：
    //   1. deps.optimizer.web.include — vite 预打包转换该依赖（web/jsdom 环境）
    //   2. server.deps.inline — 兼容回退，强制服务端转换
    //   3. server.deps.fallbackCJS — vitest 4 专用，遇到 CJS require 自动 fallback 转换
    deps: {
      optimizer: {
        web: {
          include: ['@ant-design/pro-components'],
        },
      },
    },
    server: {
      deps: {
        inline: ['@ant-design/pro-components'],
        // P4-2: vitest 4 专用，遇到 CJS require 自动 fallback 转换
        fallbackCJS: true,
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
