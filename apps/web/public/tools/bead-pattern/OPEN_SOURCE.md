# 拼豆图纸生成器开源说明

图片处理在浏览器本地完成，不调用 AI 接口。

本工具的红色均值加权 RGB 色差计算局部改编自 Jett-Wu 的 Perler Beads Generator。
其余网格编辑、按用量加权的限色流程、统计与导出为平行线实现。

- 上游项目：https://github.com/Jett-Wu/Perler_Beads_Generator
- 固定提交：`aa360a1d50f9dd3d87a30354960f3f718bd412a4`
- 原始文件：`src/palette.ts` 中的 `colorDistance`
- 修改内容：使用距离平方避免不必要的平方根运算，支持只读颜色数组；外层增加输入边界、稳定择色和有界限色处理。
- 没有引入上游 React、Three.js、图层系统或 MARD 色卡。
- Artkal 色卡和示例图片的来源另见 [SOURCES.md](./SOURCES.md)。

## 上游 MIT 许可证

MIT License

Copyright (c) 2026 Jett-Wu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
