# 目录像素图标

- 官方项目：https://github.com/halfmage/pixelarticons
- 版本：`v2.4.1`，提交 `eefef3135a8eaf0cb748149cae12f7c8d340cbba`。
- 获取日期：2026-09-30。
- 授权：MIT，见同目录 `LICENSE-MIT.txt`。
- 许可证来源：https://raw.githubusercontent.com/halfmage/pixelarticons/eefef3135a8eaf0cb748149cae12f7c8d340cbba/LICENSE
- 文件来源：`https://raw.githubusercontent.com/halfmage/pixelarticons/eefef3135a8eaf0cb748149cae12f7c8d340cbba/svg/<文件名>`。
- 处理：直接保留上游 SVG 文件，未改路径、形状、颜色属性或视口。

包含当前页面使用的 `search.svg`、`star.svg`、`heart.svg`、`arrow-right.svg`、`chevron-down.svg`、`upload.svg`、`clock.svg`、`trophy.svg`、`chevron-left.svg`、`chevron-right.svg`、`plus.svg`、`gamepad.svg`，共 12 个文件。图标均采用 `0 0 24 24` 视口，优先显示为 24px 或其整数倍。

页面可通过 CSS 遮罩使用原始文件，并继承当前文字颜色。装饰图标应有 `aria-hidden="true"`，按钮自身保留明确的可访问名称。`star.svg` 和 `heart.svg` 是轮廓图标，选中状态可改变颜色或外部底色，不应改造上游形状。

```css
.pixel-icon {
  display: inline-block;
  width: 24px;
  height: 24px;
  background-color: currentColor;
  -webkit-mask: url('/catalog/pixel-arcade/icons/search.svg') center / contain no-repeat;
  mask: url('/catalog/pixel-arcade/icons/search.svg') center / contain no-repeat;
}
```
