# 拼豆图纸工具数据与示例来源

核对日期：2026-10-22。

## Artkal S 系列 RGB 色卡

- 官方入口：https://www.artkalfusebeads.com/pages/s-color-chart
- 使用文件：https://cdn.shopify.com/s/files/1/1323/8195/files/S_MIDI_Beads_RGB_Color_Chart_2024.pdf?v=1744686607
- 来源版本：官方入口链接的 2024 RGB 色卡；不把官网其他系列或更新后的总色数视为本工具的数据范围。
- 代码文件：`apps/web/src/features/beadPattern/palette.ts`。
- 收录范围：`S01` 至 `S159` 中具有三个数值 RGB 分量的颜色，以及 `SE01` 至 `SE17`，共 173 个色号。
- 排除范围：`S41` 金色、`S42` 银色、`S63` 铜色，原表没有提供数值 RGB；不为这些颜色推测 RGB。
- 数据由官方 PDF 的前两页提取，并核对色号集合、总数量、RGB 范围。不同色号即使具有相同 RGB 也保留，名称直接使用官方色号。
- 这里只记录色号及 RGB 参考数据，不复制原表的页面设计、商标或色卡图片，也不表示获得 Artkal 背书。
- 官方说明 RGB 仅为屏幕参考值，显示设备与实物可能有色差，不能替代查看实际豆子颜色。图纸中的色号只对应本系列，不能用于推断其他品牌的对应色号。

## 真人照片示例

- 文件：`portrait-example.png`，512 × 512，原文件未修改。
- 内容：NASA 宇航员 Eileen Collins 肖像。
- 下载来源：scikit-image `v0.25.2` 的示例数据。
- 固定版本文件：https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/astronaut.png
- 来源及权利说明：https://github.com/scikit-image/scikit-image/blob/v0.25.2/skimage/data/_fetchers.py#L355-L373
- 文档：https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.astronaut
- NASA 原始来源：https://flic.kr/p/r9qvLn
- NASA 使用说明：https://www.nasa.gov/nasa-brand-center/images-and-media/
- 文件 SHA-256：`88431cd9653ccd539741b555fb0a46b61558b301d4110412b5bc28b5e3ea6cb5`，与该版本的 `skimage/data/_registry.py` 相同。

scikit-image 的原始数据说明将该照片标为来自 NASA Great Images、无已知版权限制并已进入公有领域。NASA 的使用说明允许教育及信息用途的网页使用其一般影像；本工具仅将此照片作为解释图片转换的教学示例，署名为 NASA / Eileen Collins，经 scikit-image 提供。

本示例不作为商品、广告、工具宣传封面或背书，不表示照片中的人物、NASA 或 scikit-image 认可平行线。NASA 对商业宣传中的人物肖像及标识另有约束，不能将公有领域照片说明当作这类用途的授权。

## 像素盆栽示例

- 文件：`pixel-example.svg`。
- 作者：平行线项目本次开发中手工编写的 SVG。
- 内容：32 × 32 网格、八种颜色、透明背景的像素盆栽，不基于第三方角色或图案。
- 使用上述色卡中的颜色便于验证颜色映射；没有使用 AI 图像生成。
