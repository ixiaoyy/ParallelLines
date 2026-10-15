# 第二关花园亭顶来源

`../garden-roof-model.js` 复用 [MixAndJam/MonumentValley-LevelDesign](https://github.com/MixAndJam/MonumentValley-LevelDesign) 的 `TowerTopper.fbx`，固定提交 `265bd4d6100dfddd7cdf6ff403339b3bc37f8dba`。原模型在 [MaxTurnbull 资产目录](https://github.com/MixAndJam/MonumentValley-LevelDesign/tree/265bd4d6100dfddd7cdf6ff403339b3bc37f8dba/Assets/MaxTurnbull/MonumentValleyFiles/Props)。保留 Mix and Jam 与 Max Turnbull 署名；Max Turnbull 署名依据该源资产目录。这是社区复现项目素材，并非 ustwo 官方素材。

使用原仓库根目录的 MIT 许可。已检查的根 `LICENSE` 与 `README` 没有模型排除条款；许可全文及 `Copyright (c) 2019 Mix and Jam` 已保留在 [mix-and-jam-LICENSE.txt](./mix-and-jam-LICENSE.txt)。复制、发布或改编该模型时须一并保留版权声明和许可全文。源 FBX、色板和原许可的地址、SHA256、固定版本与导出记录见 [garden-roof-sources.json](./garden-roof-sources.json)。

原完整模型包含三个互不相连的组件。本数据只保留完整的四面葱形屋顶和檐口，共 124 个三角面；去掉独立的 20 面菱形及 172 面顶球与附属部件，第二关继续使用原有旗杆与旗。筛选没有切断三角面，也没有移动顶点或改变法线、绕序。

应用源 FBX 的旋转、缩放和位移后，XZ 边界居中、最低 Y 为 0，三轴统一除以水平宽度。模型宽 1、高 `1.0160594`；三轴等比缩放保持源屋顶比例。`parts` 分别保留色板中的 `#c9c9c9`（16 面）和 `#ffffff`（108 面），金色与场景尺寸由关卡调用方指定。

`GARDEN_ROOF_MODEL` 包含 `width`、`height`、`bounds`、`triangleCount` 和 `parts`。每组的 `data` 按每顶点 `px,py,pz,nx,ny,nz` 交错，供调用方直接以 `new Float32Array(part.data)` 注册 Tiny3D 几何。没有运行时模型解析器、Unity 脚本、插件或新增依赖；这些静态网格自身不赋予道路、机关或点击行为。
