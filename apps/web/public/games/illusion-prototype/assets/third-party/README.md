# 第五关首区复用素材

`../spire-a-models.js` 是已离线转换的静态三角数据，没有运行时 FBX / OBJ 解析器、Unity 代码、插件或新增依赖。来源文件及导出文件的 SHA256、固定版本、数量和转换方式记录在 `spire-a-models-sources.json`。

## Mix and Jam / Max Turnbull

`TowerTopper` 和 `JustLegs` 来自 [MixAndJam/MonumentValley-LevelDesign](https://github.com/MixAndJam/MonumentValley-LevelDesign)，固定提交为 `265bd4d6100dfddd7cdf6ff403339b3bc37f8dba`。模型位于 [Assets/MaxTurnbull/MonumentValleyFiles/Props](https://github.com/MixAndJam/MonumentValley-LevelDesign/tree/265bd4d6100dfddd7cdf6ff403339b3bc37f8dba/Assets/MaxTurnbull/MonumentValleyFiles/Props)。保留 Mix and Jam 与 Max Turnbull 署名；Max Turnbull 的署名依据源资产目录 `MaxTurnbull`。

使用仓库根目录声明的 MIT 许可。已检查的根 `LICENSE` 和 `README` 没有模型排除条款。原文在 `mix-and-jam-LICENSE.txt`，包含 `Copyright (c) 2019 Mix and Jam`。发布、复制或改编这些模型时须保留该版权声明及许可全文。

塔顶完整保留原模型的尖顶、檐口和全部面。应用原 FBX 的旋转与非均匀缩放后才归一化。塔顶分组色值来自 `ColourAtlas.png`，尚未乘 Unity 场景材质的 tint；亭柱在 FBX 中没有 UV 或材质，明确作为灰模供关卡指定石色。这些是社区复刻项目素材，不能称为 ustwo 原作官方模型。

## Kenney Nature Kit

`rock_tallC`、`rock_tallH`、`rock_tallJ` 来自 [Kenney Nature Kit](https://kenney.nl/assets/nature-kit) 官方素材包 2.1。该来源是下载包，没有 Git 提交编号；使用包版本及下载包 SHA256 固定来源。创作者为 [Kenney](https://kenney.nl)。

素材包声明 [Creative Commons Zero 1.0（CC0，公共领域贡献）](https://creativecommons.org/publicdomain/zero/1.0/)，允许个人、教育及商业使用，无须署名；本项目保留 Kenney 信用和原包说明。说明内容保存在 `kenney-nature-kit-LICENSE.txt`，仅统一换行并清理空白；来源清单中的许可证哈希仍对应原包文件。

OBJ 的 `usemtl` 分组和 MTL 的 `Kd` 色值保留，包括土面、草面和默认材质，没有把整块岩石改成同一色。`rock_tallH` 原文件第 51 个面为三个共线点形成的零面积三角；导出保留原面并在 `sourceZeroAreaFaces` 明确标记，该面不会绘出像素。其他四个模型没有退化三角。

## 静态数据契约

`SPIRE_A_MODELS` 仅包含 `TowerTopper`、`JustLegs` 及上述三种岩石。每模型有 `width`、`height`、`bounds`、`triangleCount` 和 `parts`。每组有材质名、RGB 数字色值、三角数及 `data`；`data` 按每顶点 `px,py,pz,nx,ny,nz` 交错，调用方可直接使用 `new Float32Array(part.data)` 注册 `Tiny3D.createGeometry()`。

全部模型最低 Y 为 0、XZ 边界居中、最大 X/Z 轴向宽为 1，三轴统一除以同一宽度，保持原高度比例。调用方三轴等比缩放时才维持作者模型比例；几何没有预先赋予道路、机关、遮挡或点击行为，这些属性由关卡调用方决定。

`rock_tallC` 的一个极细三角面因 OBJ 小数截断出现绕序与法线相反；转换时仅交换角点顺序，不移动顶点。`rock_tallH` 保留源文件第 51 个零面积面，渲染不产生像素。两项均记录在来源清单和模型元数据中。

首区为手机画面将 `JustLegs` 的细柱向内增厚 25%，保留柱架外边界、高度和原网格面，并按逆转置修正法线。中央净宽仍大于角色完整身体宽度；道路和机关状态由现有关卡负责。
