<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

Use the `/trellis:start` command when starting a new session to:
- Initialize your developer identity
- Understand current project context
- Read relevant guidelines

Use `@/.trellis/` to learn:
- Development workflow (`workflow.md`)
- Project structure guidelines (`spec/`)
- Developer workspace (`workspace/`)

If you're using Codex, project-scoped helpers may also live in:
- `.agents/skills/` for reusable Trellis skills
- `.codex/agents/` for optional custom subagents

Keep this managed block so 'trellis update' can refresh the instructions.

<!-- TRELLIS:END -->

---

# 本地验证与测试约定

- **不要默认运行 `pnpm test:api`**：本地测试数据库并不是默认的 `127.0.0.1:3306/parallellines_test`，直接跑会因 MySQL 连接被拒绝产生无效失败。
- 只有在用户明确要求，或用户说明测试数据库已按当前环境配置就绪时，才运行 `pnpm test:api`。
- API 改动默认做轻量验证：`git diff --check`、相关 Python 文件 `python -m py_compile ...`，以及必要的迁移/schema 语法检查。
- Web 改动可默认运行 `pnpm typecheck:web`。

---

# 品牌 Logo 规范（禁止顺手修改）

- 当前正式站点 Logo 是 `apps/web/public/logo-lines-mark.png`，后台默认配置是 `brand_logo_url="/logo-lines-mark.png"`；浏览器图标是 `apps/web/public/favicon.svg`，默认配置是 `brand_favicon_url="/favicon.svg"`。
- Logo / favicon / 品牌图形属于受保护品牌资产。普通性能优化、页面样式调整、主题色调整、布局重构、组件拆分时，**禁止**替换、重绘、删除、重命名或改默认路径。
- 允许后台管理员通过已有 `brand_logo_url` 配置预览/保存运行时 Logo；但代码里的默认 Logo、内置资源和旧 Logo 兼容映射不能借普通需求顺手改。
- 真正换 Logo 必须是独立、明确的产品/设计需求，并同步检查：`apps/web/src/app/layouts/AppShell.vue`、`apps/web/src/app/layouts/AppShell.scss`、`apps/web/public/*logo*`、`apps/api/app/services/admin.py`、`.trellis/spec/frontend/site-theme-i18n-branding.md`、`.trellis/spec/backend/site-theme-i18n-branding.md`。
- 禁止把 `/logo-lines.png`、`/logo.png`、`/brand-mark.svg` 或 `/favicon.svg` 当作顶栏默认 Logo 的替代品；如需兼容旧值，应继续回退到 `/logo-lines-mark.png`。

---

# 前端配色与按钮规范（ParallelLines / apps/web）

**修改配色前必读。** 不要凭感觉改渐变或「更现代」的实心色；全局只改下面列出的源文件，页面里尽量用 CSS 变量。

## 唯一配置源（改主按钮色必须同步检查整表）

| 用途 | 文件 | 说明 |
|------|------|------|
| **全站主按钮（权威）** | `apps/web/src/shared/styles/button-surfaces.scss` | `--btn-primary-*` **写死 `#409EFF`**，不读 `--primary` |
| 全局设计令牌 | `apps/web/src/shared/styles/tokens.scss` | `--primary: #409eff`（链接、焦点等） |
| Ant Design 运行时主题 | `apps/web/src/app/App.vue` | `theme.token.colorPrimary` / `components.Button` 均为 `#409EFF` |
| 站点品牌运行时注入 | `apps/web/src/shared/theme/siteBranding.ts` | 读后台 `brand_primary_color` 改 `--primary`；**同时强制写回 `--btn-primary-* = #409EFF`** |
| 后台默认品牌色 | `apps/api/app/services/admin.py` | `brand_primary_color` 默认 `#409EFF`（仅新装/未改过库时） |
| 版块 / 标签 tone | `apps/web/src/shared/theme/boardPalette.ts` | 与主按钮蓝无关 |
| `UiButton` | `apps/web/src/shared/ui/Button.vue` | `primary` 走 Ant + `button-surfaces` |
| 顶栏通知中心 | `apps/web/src/features/notifications/components/NotificationBell.*` | 主题点缀用 `--btn-primary-*`，勿再用 `--accent-geek` 绿 |

注入顺序：`main.ts` → `tokens.scss` → `button-surfaces.scss` → 页面加载后 `AppShell` 调用 `applySiteBranding()`。

### 已避免的复发点（2026-05 按钮偏深问题）

1. 后台默认曾是旧深蓝品牌色，`siteBranding` 覆盖 `--primary` → 用 `var(--primary)` 的按钮变深蓝。**现主按钮只用 `--btn-primary-*`，已脱钩。**
2. `App.vue` 曾用非规范蓝色，与 SCSS 不一致。**现已对齐 `#409EFF`。**
3. `siteBranding` 曾把 `--primary-hover` 与深色标题色混色。**已改为与白色混亮。**

### 仍可能「看起来不像 #409EFF」的情况（非主按钮）

| 场景 | 原因 | 处理 |
|------|------|------|
| 链接、标签、图标高亮 | 仍用 `--primary`，跟随后台品牌色 | 后台「品牌主色」改为 `#409EFF`，或改 `siteBranding` 默认值 |
| 新版块页排序 Tab 选中 | 用版块 `--board-mark-bg` 浅底深字 | **设计如此**，不是主按钮 |
| 新页面手写 `background: var(--primary)` 当按钮 | 未走 `--btn-primary-*` | Code review / 改用 `UiButton` 或 `var(--btn-primary-bg)` |
| 数据库里仍是旧深蓝品牌色 | 只影响 `--primary`，不影响主按钮 | 可选：管理后台改设置，或跑 SQL 更新 `brand_primary_color` |
| 侧栏「本周热议」序号 `.rank` | 曾用 `var(--primary)` + 灰底 | **透底**：浅蓝半透明底 + `#409EFF` 数字（非实心按钮） |

## 主色与主按钮（禁止擅自改成浅底深字或渐变按钮）

产品约定：**Element UI 经典主色**，主 CTA 为 **实心 `#409EFF` + 白色文字**。

```text
--primary:         #409eff
--primary-hover:   #66b1ff   /* 悬停略亮 */
--primary-active:  #3a8ee6   /* 按下略深 */
--btn-primary-fg:  #ffffff   /* 主按钮文字始终白色 */
```

### 悬停两套语义（勿混用）

| 类型 | 默认 | 悬停 | 用于 |
|------|------|------|------|
| **实心** `--btn-primary-*` | `#409EFF` 底 + 白字 | `#66B1FF` 底 + 白字 | 发布、登录、实心 Tab 选中 |
| **透底** `--theme-soft-*` | 12% 透明蓝底 + `#409EFF` 字 | 18% 透明蓝底 + `#66B1FF` 字 | 热议序号、标签、全部已读、次要按钮 |

透底元素 **禁止** 悬停时用 `var(--btn-primary-bg-hover)` 铺实心亮蓝底。

- `button-surfaces.scss` 统一覆盖 `ant-btn-primary` 与 `--btn-primary-*` / `--theme-soft-*` 变量。
- 各页自定义 CTA（`RouterLink`、`.hero-link`、`.ask-link`、`.open-board-link` 等）应使用 **`var(--btn-primary-*)`**，不要写死渐变或 `var(--gradient-brand)` 当按钮底。
- **`UiButton tone="primary"`**：蓝底白字（由 `button-surfaces` 驱动）。
- **`UiButton tone="subtle"`**：浅底 `#e0f2fe`（`--bg-selected`）+ `--primary` 文字，用于次要操作。
- **`UiButton tone="success"`**：实心 `#10b981` + 白字（认领、通过等），不要改成浅绿底深字。
- **`UiButton tone="ghost"` / `danger`**：保持现有语义，勿与 primary 混用。

### 不要做的事

- 不要把主按钮改成 **浅蓝底 + 深蓝字**（曾误改，已恢复）。
- 不要用 **`--gradient-brand`** 做主按钮背景（渐变仅装饰，见下）。
- 不要把 `--primary` 改成 非规范蓝色等，除非产品明确要求。

## 品牌渐变（仅装饰，非按钮）

`tokens.scss` 中的 `--gradient-brand` 用于 **Hero 标题「平行线」文字裁剪**、少量视觉点缀，**不用于可点击主按钮**。

```text
--gradient-brand: 135deg #6dd0fa → #5ec4f4 → #66d4cb（柔和青蓝，非 #409EFF 实心）
```

## 版块色 vs 主色蓝（职责分离）

- **蓝色 `#409EFF`**：全站主 CTA（发布、登录提交、筛选 pill「全部」选中、链接型主按钮等）。
- **彩色 tone**（`boardPalette.ts`）：版块卡片、标签、版块页 Hero 徽标、**版块内排序 Tab 选中**（浅底 `--board-mark-bg` + 深字 `--board-mark-fg`），**不要**用主色蓝覆盖版块个性色。

### `boardPalette.ts` slug → tone（摘要）

| tone | slug | accent（强调色） |
|------|------|------------------|
| 1 | resources, experience, engineering, dev | `#ea580c` 暖橙 |
| 2 | health, qna, questions, support | `#65a30d` 柠绿 |
| 3 | news, frontier, frontend | `#6366f1` 紫 |
| 4 | announcements, official | `#ca8a04` 金 |
| 5 | reading, plugins | `#db2777` 粉 |
| 6 | feedback, lounge, chat, community | `#475569` 灰 |

未映射 slug / 标签名：哈希稳定分配到 1–6。修改色值只改 `BOARD_PALETTE`，刷新即全局生效。

版块 Hero 徽标（`.board-hero__mark`）：**浅色底** `--board-mark-bg` + **深色图标** `--board-accent`，不用深色渐变块 + 白图标。

## 文字与背景（常用）

```text
--title: #334155    --text: #475569    --muted: #94a3b8
--bg-app: #f8fafc   --bg-surface: #ffffff   --border: #e2e8f0
--accent-geek: #10b981   /* 高信号 / 成功点缀 */
```

## 改色检查清单

1. 主按钮是否仍通过 `button-surfaces.scss` / `--btn-primary-*`？
2. 版块相关是否只动 `boardPalette.ts`？
3. 是否在单页 SCSS 里写死了 `#409eff` 以外的主按钮色？
4. 排序 Tab（版块页）是否仍为 **版块 tone 浅底深字**，而非全局蓝实心？
5. 改完后刷新首页、版块页、发帖页各看一个 primary 按钮。
