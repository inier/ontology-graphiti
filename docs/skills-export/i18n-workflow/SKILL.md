---
name: i18n-workflow
description: 前端国际化工作流技能，用于处理中文作为 key 的 i18n 方案。包含翻译 key 提取、locale 文件创建、语言同步等辅助脚本。当用户需要国际化新页面、添加新语言支持、提取翻译 key、同步 locale 文件时使用此技能。
id: odap.l16.i18n-workflow-skill
status: vendor
owner: vendor
version: ''
layer: L16
concern: vendor-skill
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
---

# 国际化工作流技能 (i18n-workflow)

## 方案概述

本技能适用于采用 **"中文作为 i18n key"** 国际化方案的 React + i18next 项目：
- 组件中使用 `t('中文文本')` 调用
- `zh-CN` locale 文件中 key = value = 中文原文
- 其他语言 locale 文件中 key = 中文，value = 对应语言翻译
- 通过 `parseMissingKeyHandler: (key) => key` 兜底，缺失翻译时显示 key 本身（即中文）

## 前提条件

目标项目需满足以下结构约定：
1. 前端源码包含 `.tsx` 文件，使用 `t('中文')` 调用进行翻译
2. locale 文件按模块组织：`<modules-dir>/<module>/locales/<lang>/<namespace>.json`
3. 以 `zh-CN` 为基准语言，其他语言（如 `en-US`、`ja-JP`）与之对齐
4. i18next 配置包含 `fallbackLng: 'zh-CN'` 和 `parseMissingKeyHandler: (key) => key`

## 核心工具

### 脚本目录

```
scripts/
├── extract-keys.py              # 从代码中提取所有 t('中文') 调用的 key
├── create-locale.py             # 创建新语言的 locale 文件（支持多模块）
├── sync-locales.py              # 同步各语言 locale 文件（支持多模块）
└── translate-locale-from-cn.py  # 从中文翻译到目标语言（支持多模块，含术语映射）
```

### 使用方式

```bash
# 提取所有翻译 key（--src 默认为 src）
python scripts/extract-keys.py --src <源码目录>

# 提取并对比 locale 文件，找出缺失的 key
python scripts/extract-keys.py --src <源码目录> --locale <locale文件> --missing

# 创建新语言（如 ja-JP）— 自动覆盖所有模块
python scripts/create-locale.py --lang ja-JP --name "日本語" --modules <modules目录>

# 同步 locale 文件（找出缺失的 key）— 覆盖所有模块
python scripts/sync-locales.py --modules <modules目录>

# 同步并自动补充缺失的 key（使用中文作为默认值）
python scripts/sync-locales.py --modules <modules目录> --fix

# 从中文批量翻译到目标语言（使用前需填充 term_map）
python scripts/translate-locale-from-cn.py --dest ja-JP --modules <modules目录>

# 强制覆盖已有翻译
python scripts/translate-locale-from-cn.py --dest ja-JP --modules <modules目录> --overwrite
```

## 工作流程

### 1. 新增页面国际化

```
步骤1: 使用 extract-keys.py 提取代码中的字面量中文 key
步骤2: 人工审查常量数组（如 TOOL_SPECS / STATUS_OPTIONS 等）中的
       中文 label / desc / title 字段（extract-keys.py 检测不到动态 t() 调用，见 Q5）
步骤3: 将缺失的 key 添加到对应模块的 zh-CN/*.json（key=value=中文）
       注意：多行 key（含 \n）必须使用真实换行符，见 Q6
步骤4: 在其他语言 *.json 中添加对应翻译
步骤5: 运行 sync-locales.py 验证三语言完整性
步骤6: 运行 npx tsc --noEmit 验证编译通过
```

### 2. 添加新语言支持

```
步骤1: 使用 create-locale.py 创建新语言目录和文件（自动覆盖所有模块）
步骤2: 在 i18n 配置中添加新语言类型
步骤3: 在语言切换组件中添加切换选项
步骤4: 填充 translate-locale-from-cn.py 的 term_map 术语映射表
步骤5: 使用 translate-locale-from-cn.py 批量翻译
步骤6: 测试语言切换功能
```

### 3. 同步翻译文件

```
步骤1: 运行 sync-locales.py 找出缺失的翻译 key
步骤2: 补充缺失的翻译
步骤3: 再次运行验证
```

## 关键约束

1. **组件内使用 `t('中文文本')`**：直接包裹中文原文
2. **组件外常量映射**：移入组件内部，用 `useMemo` 包裹，依赖 `[instance.language]` 或 `[i18n.language]`
3. **useMemo 依赖**：使用 `instance.language` / `i18n.language` 而非 `t`（`t` 引用稳定不会触发重渲染）
4. **变量插值**：使用 `t('共 {{n}} 个', { n: total })` 语法
5. **保留不翻译内容**：`console.*` 日志、代码注释、API 路径、技术标识符、测试文件
6. **TypeScript 编译验证**：`npx tsc --noEmit`

## i18next 配置参考

```typescript
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'zh-CN',
    ns: namespaces,
    defaultNS: 'common',
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
    returnEmptyString: false,
    parseMissingKeyHandler: (key) => key,  // 缺失翻译时返回 key 本身
    missingKeyHandler: (_lng, _ns, key) => {
      console.warn(`[i18n] Missing translation key: ${key}`);
    },
  });
```

## 常见问题

### Q1: 切换语言后部分文本未更新

**原因**：`useMemo` 依赖了 `t` 而非 `instance.language`

**解决**：
```tsx
// ❌ 错误
const items = useMemo(() => list.map(i => t(i.label)), [t]);

// ✅ 正确
const items = useMemo(() => list.map(i => t(i.label)), [i18n.language]);
```

### Q2: 缺失翻译 key 时显示 undefined

**原因**：`returnEmptyString: false` 配置缺失

**解决**：确认 i18next 配置中包含 `returnEmptyString: false`

### Q3: 组件外常量无法使用 t()

**原因**：`useTranslation` / `useI18n` 是 React Hook，只能在组件内部使用

**解决**：将常量映射移入组件内部，用 `useMemo` 包裹

### Q4: extract-keys.py 漏检动态 t() 调用（常量数组中的中文 label）

**原因**：`extract-keys.py` 使用正则 `t\('([^']+)'\)` 仅匹配**字面量字符串参数**（如 `t('中文')`），无法检测动态调用如 `t(tool.category)`、`t(opt.label)`、`t(item.title)`。当组件使用常量数组（如 `TOOL_SPECS`、`STATUS_OPTIONS`、`SOURCE_TYPE_OPTIONS`）并通过 `t(opt.label)` 翻译 label 字段时，这些中文 label 不会被提取，导致 locale 文件缺失对应 key。

**典型场景**：
```tsx
// 常量数组中的中文 label（extract-keys.py 检测不到）
const SOURCE_TYPE_OPTIONS = [
  { label: '文本', value: 'text' },
  { label: '事件', value: 'event' },
];
// 组件内通过 useMemo + t() 翻译
const options = useMemo(
  () => SOURCE_TYPE_OPTIONS.map(opt => ({ ...opt, label: t(opt.label) })),
  [i18n.language],
);
```

**解决**：
1. 人工审查所有常量数组中的中文 label / title / desc 字段
2. 将这些中文文本作为 key 添加到对应模块的 `zh-CN/*.json`（key=value=中文）
3. 在 `en-US/*.json` 和 `ja-JP/*.json` 中补充翻译
4. 运行 `sync-locales.py` 验证三语言完整性

**排查命令**（查找常量数组中的中文 label）：
```bash
# 使用 ripgrep
rg "label: '[^']*[\u4e00-\u9fff]" --type tsx
rg "desc: '[^']*[\u4e00-\u9fff]" --type tsx
```

### Q5: 多行 key 编码不一致（\n 字面量 vs 真实换行）

**原因**：当代码中有 `t('第一段…\n---\n第二段…')` 时，TypeScript/JS 运行时会将 `\n` 解释为**真实换行符**。但 `extract-keys.py` 的正则从源码文本中提取的是**字面量 `\n`**（反斜杠+n 两个字符），导致 locale 文件中的 key 与运行时 `t()` 调用的 key 不匹配。

**症状**：
- `sync-locales.py` 报告某 key 在 zh-CN 缺失，但 en-US/ja-JP 不缺失（或反之）
- 用 `repr()` 检查 key：zh-CN 显示 `'...\\n...'`（字面量），en-US 显示 `'...\n...'`（真实换行）

**解决**：locale 文件中的多行 key 必须使用**真实换行符**（JSON 中转义为 `\n`），与运行时 `t()` 调用一致。如发现字面量 `\n` 的错误 key，需删除并重新添加正确 key：
```python
import json
wrong_key = "文本…\\n---\\n文本…"   # 字面量 backslash-n
correct_key = "文本…\n---\n文本…"   # 真实换行
# 删除 wrong_key，添加 correct_key
```

## 检查清单

新增功能时，请按以下清单检查：
- [ ] 所有用户可见的中文文本已用 `t()` 包裹
- [ ] 带变量的文本使用 `{{var}}` 插值语法
- [ ] 组件外常量映射已移入组件内部
- [ ] `useMemo` / `useEffect` 依赖使用 `i18n.language` 而非 `t`
- [ ] **常量数组中的中文 label / desc / title 字段已手动添加到 locale 文件**（extract-keys.py 检测不到动态 `t(opt.label)` 调用，见 Q4）
- [ ] **多行 key（含 `\n`）在 locale 文件中使用真实换行符**（见 Q5）
- [ ] 对应模块的 `zh-CN/*.json` 已添加新 key
- [ ] 其他语言 `*.json` 已添加对应翻译
- [ ] `console.*` 日志和代码注释保留中文未动
- [ ] 测试文件未修改
- [ ] TypeScript 编译通过
- [ ] `sync-locales.py` 各语言对齐
- [ ] 浏览器验证语言切换效果

## 术语映射扩展

如需扩展翻译覆盖范围，编辑 `translate-locale-from-cn.py` 中的 `term_map` 字典，添加新的中文到目标语言映射。

```python
term_map = {
    # 通用 UI 术语（日文示例）
    "取消": "キャンセル",
    "删除": "削除",
    "编辑": "編集",
    "添加": "追加",
    "搜索": "検索",
    "刷新": "更新",
    "确认": "確認",
    "提交": "送信",
    "重置": "リセット",
    "导出": "エクスポート",
    "导入": "インポート",
    "下载": "ダウンロード",
    "上传": "アップロード",
    "关闭": "閉じる",
    "返回": "戻る",
    "确定": "OK",
    "名称": "名前",
    "描述": "説明",
    "状态": "ステータス",
    "类型": "タイプ",
    "创建时间": "作成時間",
    "更新时间": "更新時間",
    # ... 添加项目领域术语
}
```
