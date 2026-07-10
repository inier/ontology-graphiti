# antd v6 废弃 API 清理报告（2026-07-09）

## 起因
控制台出现 `Warning: [antd: Spin] 'tip' is deprecated. Please use 'description' instead.`。
项目 `package.json` 中 antd 已是 `^6.3.5`（**并非版本不一致**，而是 v6 自身把若干旧属性标记废弃）。
用户要求「举一反三，全面清理类似警告」。

## 方法（证据驱动，杜绝误伤）
1. 解析 `node_modules/antd/es/**/*.d.ts` 的 `@deprecated` 注解（antd 权威废弃清单，共 251 条）。
2. 用 **brace-aware 组件作用域匹配**：只在对应组件（如 `<Spin`、`<Alert`）的开标签内重命名属性，绝不触碰其他组件或嵌套子元素上的同名属性。
3. 复扫非属性型废弃（如 `TabPane`、`FloatButton.BackTop`、`message.warn`、`overlay=`），确认代码中不存在。

## 修复清单（共 26 个文件）
| 废弃用法 | 替换为 | 处数 | 代表性文件 |
|---|---|---|---|
| `Spin.tip` | `description` | 4 | `App.tsx`、`MinioAdminPage.tsx`、`SettingsPage.tsx`、`DocumentViewer.tsx` |
| `Alert.message` | `title` | 17 | I18nAdminPage / KnowledgeBase / 多个 ontology 组件等 |
| `Alert.onClose` | `closable={{ onClose: ... }}` | 4 | WebCrawlPanel / WebSearchPanel / DocumentImporter / SettingsPage |
| `Card.bodyStyle` | `styles={{ body: ... }}` | 4 | RoleMenuAssigner×2 / MenuConfigPage / MinioAdminPage |
| `Steps.direction` / `Space.direction` | `orientation` | 2 | BusinessEntityManager / ChannelCard |
| `Progress.trailColor` | `railColor` | 1 | OntologyBuildProgress |

## 正确保留（非废弃，未改动）
- `Descriptions.bordered`：v6 **未**废弃（仅 `items`/`labelStyle`/`contentStyle` 废弃）。
- `Upload.maxCount`：合法 v6 属性（被误认为废弃的 `Avatar.Group.maxCount` 才是废弃）。
- `Space.separator`：合法 v6 属性（废弃的是旧 `split`）。
- 项目自研 `shared/components/molecules/Card.tsx` 的 `bordered` 属性：非 antd，不动。
- 业务代码中的 `console.warn(...)`：自有日志，无关。

## 验证
- 复跑扫描脚本：`found 0 potential deprecated usages` ✅
- 修复过程中修复了一处脚本引入的 `Alert.onClose` 双层 `{}` 包箭头函数问题，最终 JSX 合法。

## 关于「更新到最新版本」
`^6.3.5` 的 caret 已允许安装最新 6.x 补丁；**警告是靠改代码消除，而非升版本**。无需强升主版本（避免引入回归）。

## 复用工具
- `scripts/audit_antd_deprecations.py` — 扫描器（解析 @deprecated + 组件作用域匹配）
- `scripts/fix_antd_deprecations.py` — 修复器（brace-aware 作用域替换）
- 技能 `antd-deprecation-audit` — 固化本方法论
