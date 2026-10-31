---
id: odap.l16.i18n-workflow-readme
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

# i18n-workflow（通用版）

适用于 **React + i18next** 项目的国际化工作流技能，采用「中文作为 i18n key」方案。

## 适用条件

目标项目需满足：
1. 使用 React + react-i18next
2. locale 文件按模块组织：`<src>/modules/<module>/locales/<lang>/<namespace>.json`
3. 以 `zh-CN` 为基准语言
4. i18next 配置 `fallbackLng: 'zh-CN'` + `parseMissingKeyHandler: (key) => key`

如果不满足条件 2（模块结构不同），脚本仍可用 — 通过 `--modules` 参数指定实际路径。
如果不满足条件 3-4（不用中文作为 key），则本技能不适用。

## 安装方式

### 方式 1：安装为 Trae 项目级 skill

```bash
# 复制到目标项目的 .trae/skills/ 目录
cp -r docs/skills-export/i18n-workflow <目标项目>/.trae/skills/i18n-workflow
```

### 方式 2：安装为 Trae 用户级 skill（跨项目共享）

```bash
# 复制到用户级 skills 目录
cp -r docs/skills-export/i18n-workflow ~/.trae-cn/skills/i18n-workflow
# 或（Mac/Linux）
cp -r docs/skills-export/i18n-workflow ~/.trae/skills/i18n-workflow
```

### 方式 3：作为独立工具使用

```bash
# 直接复制 scripts/ 目录到任意位置
cp -r docs/skills-export/i18n-workflow/scripts /path/to/your-project/i18n-tools
cd /path/to/your-project
python i18n-tools/extract-keys.py --src src
```

## 使用前配置

### 1. 确认 modules 路径

所有脚本通过 `--modules` 参数指定 locale 文件的模块根目录。默认值为 `src/modules`，按项目实际情况调整：

```bash
# 常见路径示例
--modules src/modules          # React 标准结构
--modules apps/web/src/modules # Monorepo 结构
--modules src/locales          # 扁平结构（需调整脚本）
```

### 2. 填充术语映射表（translate-locale-from-cn.py）

编辑 `scripts/translate-locale-from-cn.py`，在 `term_map` 字典中添加项目术语翻译：

```python
term_map = {
    # 通用 UI 术语
    "取消": "キャンセル",
    "删除": "削除",
    # 项目领域术语
    "本体": "オントロジー",
    "推理": "推論",
    # ...
}
```

### 3. 确认 i18next 配置

确保项目的 i18next 初始化包含以下关键配置：

```typescript
i18n.init({
  fallbackLng: 'zh-CN',
  returnEmptyString: false,
  parseMissingKeyHandler: (key) => key,
  // ...
});
```

## 快速验证

安装后运行以下命令验证：

```bash
# 1. 提取代码中的翻译 key
python .trae/skills/i18n-workflow/scripts/extract-keys.py --src src

# 2. 检查各语言 locale 文件完整性
python .trae/skills/i18n-workflow/scripts/sync-locales.py --modules src/modules

# 3. TypeScript 编译检查
npx tsc --noEmit
```

## 脚本说明

| 脚本 | 功能 | 已知限制 |
|------|------|----------|
| `extract-keys.py` | 从 `.tsx` 提取 `t('中文')` 字面量 key | 不检测动态调用 `t(var)`，常量数组中文 label 需人工审查（见 SKILL.md Q4） |
| `sync-locales.py` | 对比各语言 locale 文件，找出缺失 key | — |
| `create-locale.py` | 基于 zh-CN 创建新语言 locale 文件 | — |
| `translate-locale-from-cn.py` | 基于 term_map 批量翻译 | 需手动填充 term_map；翻译质量取决于映射表覆盖度 |

## 与本项目（ontology-graphiti）版本的差异

本通用版剥离了以下项目特定内容：
- ❌ `sync-menu-names.py`（依赖 DB 菜单种子数据 + `resolveMenuName()` 机制）
- ❌ 菜单国际化工作流和常见问题（Q4 菜单名称失效 / Q7 menu-config 设计如此）
- ❌ 项目特定文件索引（ontology/simulation/shared 等模块名）
- ❌ `translate-locale-from-cn.py` 中 1672 行的项目领域术语映射（term_map 清空为模板）
- ✅ 所有脚本添加 `--modules` / `--src` 参数，不再硬编码项目路径
- ✅ 保留全部通用 i18n 最佳实践和常见问题（Q1-Q5）

## 许可

随项目许可。
