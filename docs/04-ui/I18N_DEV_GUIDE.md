# 前端国际化开发指南 (I18n Dev Guide)

> 适用范围：`apps/web` 前端应用
> 方案版本：v1.0（中文作为 key）
> 最后更新：2026-07-21

---

## 1. 方案概述

本项目采用 **"中文作为 i18n key"** 的国际化方案，核心思想：

- 组件中使用 `t('中文文本')` 调用
- `zh-CN` locale 文件中 key = value = 中文原文
- `en-US` locale 文件中 key = 中文，value = 英文翻译
- 通过 `parseMissingKeyHandler: (key) => key` 兜底，缺失翻译时显示 key 本身（即中文）

### 方案优势

1. **零侵入迁移**：原有硬编码中文只需包裹 `t()` 即可，无需建立 key 映射表
2. **可读性强**：代码中 `t('创建工作空间')` 比 `t('workspace.create.title')` 更易理解
3. **渐进式国际化**：未翻译的 key 在 en-US 下回退显示中文，不影响功能
4. **降低维护成本**：无需维护 key 命名约定，新增功能直接用中文 key

### 方案限制

1. **中文 key 长度较长**：相比短 key，JSON 文件体积稍大
2. **key 重命名困难**：修改中文文本等于修改 key，需要同步更新两个 locale 文件
3. **重复文本无法自动复用**：相同含义的不同中文会被视为不同 key

---

## 2. 文件结构

```
apps/web/src/modules/shared/
├── hooks/
│   └── useI18n.ts              # i18n hook 封装
├── stores/
│   └── i18nStore.ts            # i18next 配置和状态管理
└── locales/
    ├── zh-CN/
    │   └── common.json         # 中文 locale (key=value=中文)
    └── en-US/
        └── common.json         # 英文 locale (key=中文, value=英文)
```

### 2.1 i18nStore.ts 核心配置

```typescript
{
  fallbackLng: 'zh-CN',
  parseMissingKeyHandler: (key) => key,   // 缺失翻译返回 key 本身
  returnEmptyString: false,
  returnNull: false,
  // common 命名空间在 skipInvertNamespaces 中，直接使用中文作为 key
}
```

### 2.2 useI18n Hook

```typescript
import { useI18n } from '@/modules/shared/hooks/useI18n';

function MyComponent() {
  const { t, instance, locale } = useI18n();
  // t: 翻译函数
  // instance: i18next 实例（用于读取 instance.language）
  // locale: 当前语言代码（'zh-CN' | 'en-US'）
  return <div>{t('你好')}</div>;
}
```

---

## 3. 使用方法

### 3.1 基本用法

```tsx
import { useI18n } from '@/modules/shared/hooks/useI18n';

function MyComponent() {
  const { t } = useI18n();

  return (
    <div>
      <h1>{t('工作空间管理')}</h1>
      <Button>{t('创建')}</Button>
      <Input placeholder={t('请输入名称')} />
      <message.success(t('操作成功'))}
    </div>
  );
}
```

### 3.2 变量插值

使用 i18next 标准的 `{{var}}` 语法：

```tsx
// 组件中
t('共 {{n}} 条', { n: total })
t('用户 {{name}} 已登录', { name: username })

// zh-CN/common.json
{
  "共 {{n}} 条": "共 {{n}} 条",
  "用户 {{name}} 已登录": "用户 {{name}} 已登录"
}

// en-US/common.json
{
  "共 {{n}} 条": "Total {{n}} items",
  "用户 {{name}} 已登录": "User {{name}} has logged in"
}
```

### 3.3 组件外常量映射的处理

**问题**：组件外部定义的常量映射无法直接调用 `t()`（因为 hook 只能在组件内使用）。

**解决方案**：将常量映射移入组件内部，用 `useMemo` 包裹：

```tsx
// ❌ 错误：组件外无法使用 t()
const STATUS_LABELS = {
  active: t('活跃'),      // 报错
  inactive: t('停用'),    // 报错
};

function MyComponent() {
  return <Tag>{STATUS_LABELS[status]}</Tag>;
}

// ✅ 正确：移入组件内部
function MyComponent() {
  const { t } = useI18n();

  const statusLabels = useMemo(() => ({
    active: t('活跃'),
    inactive: t('停用'),
  }), [t]);   // 依赖 t 以响应语言切换

  return <Tag>{statusLabels[status]}</Tag>;
}
```

### 3.4 语言切换响应

**关键点**：`t` 函数引用稳定，不会随语言变化触发重渲染。需要使用 `instance.language` 作为 `useMemo`/`useEffect` 依赖：

```tsx
function MyComponent() {
  const { t, instance } = useI18n();

  // ❌ 错误：依赖 t 不会响应语言切换
  const menuItems = useMemo(() => items.map(i => t(i.label)), [t]);

  // ✅ 正确：依赖 instance.language
  const menuItems = useMemo(() => items.map(i => t(i.label)), [instance.language]);

  return <Menu items={menuItems} />;
}
```

---

## 4. 开发规范

### 4.1 新增功能国际化流程

1. **编写组件时直接使用 `t()` 包裹中文**：
   ```tsx
   <Button>{t('新增用户')}</Button>
   ```

2. **同步更新 locale 文件**：
   - 在 `zh-CN/common.json` 添加 `"新增用户": "新增用户"`
   - 在 `en-US/common.json` 添加 `"新增用户": "Add User"`

3. **验证**：
   - 切换语言检查 UI 显示
   - 运行 `cd apps/web && npx tsc --noEmit` 确保无类型错误

### 4.2 翻译规范

| 场景 | 中文 key | 英文翻译 | 说明 |
|------|----------|----------|------|
| 按钮 | `新增` | `Add` | 简洁，首字母大写 |
| 表格列标题 | `创建时间` | `Created At` | 首字母大写 |
| 表单标签 | `用户名` | `Username` | 单数形式 |
| 表单 placeholder | `请输入用户名` | `Please enter username` | 句子形式 |
| 消息提示 | `保存成功` | `Saved successfully` | 句子形式 |
| 变量插值 | `共 {{n}} 条` | `Total {{n}} items` | 保留 `{{n}}` |
| 技术术语 | `OPA 策略` | `OPA Policy` | 保持英文术语 |
| 枚举值 | `启用` / `禁用` | `Enabled` / `Disabled` | 状态枚举 |

### 4.3 保留不翻译的内容

以下内容**不需要**用 `t()` 包裹：

1. **console 日志**：`console.error('加载数据失败', error)` — 开发者调试用
2. **代码注释**：`// 加载工作空间列表`
3. **API 路径和参数**：`/api/auth/users`、`POST`、`GET`
4. **技术标识符**：`system_admin`、`is_active`、`workspace_id`
5. **示例数据**：演示用的 mock 数据中的中文（如 `五虎将`）
6. **测试文件**：`*.test.tsx` 中的断言文本

### 4.4 代码风格

```tsx
// ✅ 推荐：内联使用
<Button>{t('保存')}</Button>
<Input placeholder={t('请输入名称')} />

// ✅ 推荐：复杂文本用插值
{t('共 {{n}} 条记录', { n: total })}

// ❌ 避免：拼接字符串
{t('共') + ' ' + total + ' ' + t('条')}

// ❌ 避免：在条件表达式中拼接
{`${t('删除')} ${record.name}`}

// ✅ 推荐：条件文本用多个 t() 调用
{enabled ? t('启用') : t('禁用')}

// ❌ 避免：动态拼接 key
t(`状态.${status}`)

// ✅ 推荐：用映射表
const statusMap = { active: t('活跃'), inactive: t('停用') };
{statusMap[status]}
```

---

## 5. 已国际化页面清单

截至 2026-07-21，已完成国际化的页面模块：

### 5.1 核心布局组件

| 文件 | 说明 |
|------|------|
| `shared/components/ProLayout.tsx` | 主布局，菜单国际化 |
| `shared/components/AdminLayout.tsx` | 管理后台布局 |
| `shared/components/ExtensionPanel.tsx` | 扩展区面板 |
| `shared/components/QuickActionBar.tsx` | 快捷操作栏 |
| `shared/components/TaskPanel.tsx` | 任务面板 |
| `shared/components/TabDetailPreview.tsx` | Tab 详情预览 |
| `shared/components/LanguageSwitcher.tsx` | 语言切换器 |

### 5.2 业务页面

| 模块 | 页面 | 说明 |
|------|------|------|
| shared | LoginPage | 登录页 |
| guide | GuidePage | 系统指南页 |
| roles | RoleManager | 角色管理 |
| roles | UserManagement | 用户管理 |
| workspace | WorkspacePage | 工作空间管理 |
| workspace | WorkspaceManager | 工作空间管理（旧版） |
| audit | AuditLog | 审计日志 |
| audit | AuditTimeline | 审计时间线 |
| audit | PolicyPage | 策略管理 |
| ingest | IngestPanel | 数据摄入 |
| ingest | Simulator | 事件模拟器 |
| qa | QAPage | 智能问答 |
| qa | QueryPage | 查询页 |
| qa | EvaluationPage | 评估页 |
| agent | MyAgents | 我的智能体 |
| agent | AgentManagement | 智能体管理 |
| agent | AgentChat | 智能体对话 |
| agent | AgentPage | Agent 调度 |
| ontology | OntologyDesignerPage | 本体设计器 |
| ontology | OntologyGraphPage | 语义图谱 |
| ontology | OntologySemanticNetwork | 语义网络 |
| ontology | ObjectViewPage | 对象视图 |
| ontology | HealthDashboard | 数据健康看板 |
| ontology | GoalKanban | Goal 看板 |
| ontology | UnifiedManagementPage | 统一管理（已完整国际化） |
| semantic-admin | UslConfigPage | USL 配置 |
| semantic-admin | QualityDashboardPage | 质量指标面板 |
| semantic-admin | PipelineRunsPage | 流水线运行 |
| semantic-admin | PipelineComingSoon | 流水线（占位） |
| semantic-admin | CandidatesPage | 候选审核 |
| semantic-admin | CandidatesComingSoon | 候选审核（占位） |
| semantic-admin | ApprovalsPage | 审批工作台 |
| semantic-admin | DashboardPage | 治理仪表盘 |
| business | SmartGeneration | 智能生成 |
| business | ObjectManagement | 对象管理 |
| business | Rules | 规则 |
| business | Logic | 逻辑 |
| business | Indicators | 指标 |
| business | BusinessProcess | 业务过程 |
| simulation | StrategyDeduction | 策略推演 |
| simulation | SimulationPage | 沙箱推演 |
| simulation | SandboxManager | 沙箱管理 |
| knowledge | KnowledgePage | 知识导航 |
| knowledge | KnowledgeBase | 知识库 |
| config | PolicyManager | 策略管理器 |
| config | PolicyManagement | 策略管理 |
| system | SkillManagement | Skill 管理 |
| version | VersionHistory | 版本历史 |
| minio-admin | MinioAdminPage | MinIO 管理 |
| channels | ChannelManagementPage | 渠道管理 |

### 5.3 特殊模式页面

以下页面使用了独立的 i18n 命名空间，未采用"中文作为 key"方案：

| 文件 | 模式 | 说明 |
|------|------|------|
| `menu-config/pages/MenuConfigPage.tsx` | `useI18n('menu-config')` + 英文 key | 菜单配置 |
| `i18n-admin/pages/I18nAdminPage.tsx` | `useTranslation('i18n-admin')` + 英文 key | 国际化管理 |
| `settings/pages/SettingsPage.tsx` | `useI18n('settings')` + 中文 key | 设置页 |

### 5.4 locale 文件统计

- `zh-CN/common.json`：约 1730 条翻译
- `en-US/common.json`：约 1730 条翻译

---

## 6. 国际化管理页面说明

### 6.1 与 JSON 文件的关系

- **国际化管理页面**（`/i18n-admin`）编辑的内容保存到**后端数据库**
- **JSON 文件**是前端静态资源，构建时打包到产物中
- 页面编辑的翻译**不会**自动同步到 JSON 文件

### 6.2 新增中文的处理流程

1. 组件中直接使用 `t('新功能名称')`
2. 如果 `en-US/common.json` 中没有对应翻译，UI 会通过 `parseMissingKeyHandler` 回退显示中文
3. 手动在 `en-US/common.json` 中添加英文翻译
4. 重新构建前端应用生效

### 6.3 热更新限制

- JSON 文件修改后**需要重新构建**（`npm run build`）才能生效
- 后端数据库中的翻译可通过国际化管理页面实时编辑
- 当前未实现数据库翻译的运行时加载，所有翻译来自构建时的 JSON 文件

---

## 7. 常见问题

### Q1: 切换语言后部分文本未更新

**原因**：`useMemo` 依赖了 `t` 而非 `instance.language`，或组件未正确订阅语言变化。

**解决**：
```tsx
// ❌ 错误
const items = useMemo(() => list.map(i => t(i.label)), [t]);

// ✅ 正确
const items = useMemo(() => list.map(i => t(i.label)), [instance.language]);
```

### Q2: Tab 标题切换语言不同步

**原因**：`updateTabTitles` 只更新了固定路径，未包含动态 tab。

**解决**：遍历所有 `routeTabInfo` 条目，全部传递给 `updateTabTitles`。参考 `AdminLayout.tsx` 和 `ProLayout.tsx` 的实现。

### Q3: 缺失翻译 key 时显示 undefined

**原因**：`returnEmptyString: false` 或 `returnNull: false` 配置缺失。

**解决**：确认 `i18nStore.ts` 中配置正确：
```typescript
{
  returnEmptyString: false,
  returnNull: false,
  parseMissingKeyHandler: (key) => key,
}
```

### Q4: 组件外常量无法使用 t()

**原因**：`useI18n` 是 React Hook，只能在组件内部使用。

**解决**：将常量映射移入组件内部，用 `useMemo` 包裹，依赖 `[instance.language]`。

### Q5: 如何批量提取和补充翻译 key

使用以下命令扫描所有 `t('...')` 调用：

```powershell
# 提取所有 t('中文') 调用（PowerShell）
Select-String -Path "apps\web\src\modules\**\*.tsx" -Pattern "t\('([^']+)'\)" | 
  ForEach-Object { $_.Matches[0].Groups[1].Value } | 
  Sort-Object -Unique
```

然后将缺失的 key 添加到 `common.json`。

---

## 8. 后续工作建议

### 8.1 短期（1-2 周）

- [x] 补全 `en-US/common.json` 中质量较低的翻译（部分翻译可能不够地道）
- [x] 统一 `menu-config` 和 `i18n-admin` 模块为"中文作为 key"方案（已确认使用中文 key）
- [x] 添加 i18n 单元测试，确保关键页面切换语言正常

### 8.2 中期（1-2 月）

- [ ] 实现后端数据库翻译的运行时加载，支持热更新
- [x] 添加更多语言支持（如 `ja-JP`、`ko-KR`）
- [x] 实现翻译质量检测工具，自动发现缺失的翻译 key（通过 `extract-keys.py` 和 `sync-locales.py`）

### 8.3 长期

- [ ] 接入专业翻译平台（如 Crowdin、Lokalise）
- [ ] 实现 A/B 测试不同翻译版本
- [ ] 支持 RTL（从右到左）语言布局

---

## 9. 相关文件索引

| 文件 | 说明 |
|------|------|
| `apps/web/src/modules/shared/hooks/useI18n.ts` | i18n Hook 封装 |
| `apps/web/src/modules/shared/stores/i18nStore.ts` | i18next 配置 |
| `apps/web/src/modules/shared/locales/zh-CN/common.json` | 中文翻译 |
| `apps/web/src/modules/shared/locales/en-US/common.json` | 英文翻译 |
| `apps/web/src/modules/shared/locales/ja-JP/common.json` | 日文翻译 |
| `apps/web/src/modules/shared/locales/ko-KR/common.json` | 韩文翻译 |
| `apps/web/src/modules/shared/components/LanguageSwitcher.tsx` | 语言切换组件 |
| `apps/web/src/modules/i18n-admin/pages/I18nAdminPage.tsx` | 国际化管理页面 |
| `apps/web/src/modules/shared/stores/i18nStore.test.ts` | i18nStore 单元测试 |
| `apps/web/src/modules/shared/hooks/useI18n.test.ts` | useI18n Hook 单元测试 |
| `.trae/skills/i18n-workflow/SKILL.md` | 国际化工作流技能 |
| `.trae/skills/i18n-workflow/scripts/extract-keys.py` | 翻译 key 提取脚本 |
| `.trae/skills/i18n-workflow/scripts/create-locale.py` | 新语言创建脚本 |
| `.trae/skills/i18n-workflow/scripts/sync-locales.py` | locale 文件同步脚本 |
| `docs/07-adr/ADR-037_frontend_mobile_first_i18n.md` | i18n 架构决策记录 |

---

## 附录：国际化检查清单

新增功能时，请按以下清单检查：

- [ ] 所有用户可见的中文文本已用 `t()` 包裹
- [ ] 带变量的文本使用 `{{var}}` 插值语法
- [ ] 组件外常量映射已移入组件内部
- [ ] `useMemo`/`useEffect` 依赖使用 `instance.language` 而非 `t`
- [ ] `zh-CN/common.json` 已添加新 key
- [ ] `en-US/common.json` 已添加对应英文翻译
- [ ] `console.*` 日志和代码注释保留中文未动
- [ ] 测试文件未修改
- [ ] TypeScript 编译通过：`cd apps/web && npx tsc --noEmit`
- [ ] 浏览器验证语言切换效果
