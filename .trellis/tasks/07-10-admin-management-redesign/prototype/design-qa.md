# 后台管理改版原型 Design QA

- Source: `C:\Users\phpxi\.codex\generated_images\019f49d9-8acb-7dc3-a26c-4a63f9061d74\exec-7f59acc4-aa24-49d1-9f69-22ff9ce74d5b.png`
- Implementation: `D:\work\ParallelLines\.trellis\tasks\07-10-admin-management-redesign\prototype\qa\analytics-visible-final.png`
- Reference viewport/state: 1487 × 1058，访问与用户增长，30 天区间，默认数据状态。
- Responsive states: 1024 × 768 平板；390 × 844 手机；用户列表/详情、审核队列/详情、移动抽屉均单独验证。

## Comparison evidence

### Full-view pass

参考图与最终实现以同一 1487 × 1058 视口放入同一次对照检查。实现保留了所选「运营控制台」方向的核心结构：固定侧栏、56px 顶栏、扁平内容画布、横向筛选、六项指标、双图表与双列表。最终截图中侧栏品牌区底线为 57px、顶栏底线为 56px，视觉基线已对齐；文档宽度与滚动宽度均为 1472px，无横向溢出。

### Focused-region pass

- Reference crop: `qa/reference-focus-header-charts.png`
- Implementation crop: `qa/implementation-focus-header-charts.png`
- Region: x=225、y=56、1262 × 620，覆盖标题、刷新、日期筛选、指标带与两张趋势图。

聚焦对照确认标题层级、筛选密度、指标分隔、图表比例、轴线与图例位置一致。实现刻意只在「区间新增用户」标注“不含马甲账号”，并在增长图的辅助文本中说明该口径；没有把该口径错误地附加到独立访客。

## Five fidelity surfaces

1. **Typography** — 使用产品现有中文系统字体栈，标题、正文、指标与表格的字号/字重层级与参考一致；窄屏长邮箱可换行，没有截断关键身份信息。
2. **Spacing and layout** — 232px 侧栏、56px 顶栏和扁平分区保持稳定；桌面、平板与手机均无横向溢出。手机端用户与审核采用单页 master/detail 切换，避免原页面重叠。
3. **Colors and surfaces** — 主交互保持项目规范 `#409EFF`，成功/提醒语义分别使用绿/橙；没有渐变按钮、玻璃效果或多余卡片阴影。
4. **Assets and icons** — 使用正式 `logo-lines-mark.png`，未替换或重绘品牌资产；界面图标统一来自 Ant Design Icons，没有手绘 SVG、emoji 或占位图形。
5. **Behavior and accessibility** — 导航、日期预设、刷新、搜索筛选、用户详情保存、审核切换/处理、任务重试和邮件筛选可交互；语义控件、焦点态、ARIA 标签、减少动画偏好与移动端 40px+ 触控目标均已覆盖。

## Findings and comparison history

| Pass | Severity | Finding | Resolution | Post-fix evidence |
|---|---|---|---|---|
| Initial | P1 | 旧后台仍沿用前台顶栏与大卡片，页面信息层级不清晰。 | 重建独立后台壳层与五个统一入口。 | `qa/analytics-visible-final.png` 及五页导航实测。 |
| Initial | P1 | 用户管理在窄屏保留列表、筛选和详情，造成视觉挤压与页面重叠。 | 改为移动端列表/详情单页切换；打开详情回到顶部，返回恢复原列表位置。 | `qa/users-mobile-detail-390.png`；scroll 0 → 返回 181.5px 位置实测。 |
| Initial | P2 | 品牌区高度 76px，与 56px 顶栏底线错位。 | 品牌区收紧为 56px，并移除重复副标题。 | 品牌底线 57px、顶栏底线 56px。 |
| Initial | P2 | 用户增长排除马甲的说明曾出现在不相关指标/图例位置。 | 只保留在真实新增用户指标与增长图可访问说明中。 | 最终 DOM 与聚焦对照。 |
| Initial | P2 | 用户筛选可能让详情停留在已被过滤掉的账号。 | 由可见列表派生 active user；无结果时隐藏详情。 | 搜索“林屿”后列表与详情均为“林屿”；无结果时详情 `display:none`。 |
| Initial | P2 | 内容审核中的示例 URL 使用了阻止跳转的假链接语义。 | 改为普通内容预览文本。 | `.moderation-content-preview__link` 为 `SPAN`，页面无预览区 anchor。 |
| Final | P3 | 浏览器截图的字体抗锯齿与参考图的生成式渲染略有差异。 | 接受；不影响实际浏览器中的层级、对齐或可读性。 | 同尺寸全图与聚焦图复核。 |

没有未关闭的 P0、P1 或 P2 问题。

## Interaction and viewport verification

- 桌面 1487 × 1058：五个入口均可切换；访问增长、用户筛选、审核操作、系统重试和工作台快捷入口可用。
- 平板 1024 × 768：五页 `scrollWidth === clientWidth`；截图 `qa/analytics-tablet-1024.png`。
- 手机 390 × 844：访问增长、用户详情、审核详情、系统运行和工作台均无横向溢出；底部五项导航固定可用。
- 用户管理：搜索“林屿”后 active row 与详情同步；搜索无结果显示空状态且隐藏详情；移动详情返回恢复列表滚动位置。
- 内容审核：队列、详情、标签和处理反馈已验证；示例 URL 不再表现为可点击导航。
- Console: 0 errors, 0 warnings in final browser pass.
- React Doctor: 100 / 100, no issues found.
- Production build: `vite build` passed，3446 modules transformed。

final result: passed
