# BIRDLAND 英文原版收录

## 已确认范围

用户已授权本批验证后仅提交、推送相关改动到 `main`，先上传正式封面，再按原 CI → Deploy 流程发布到 `pingxingxian.space`。
本次不做汉化，不联系作者，不复制或托管游戏包；此前九款隐藏记录及其他项目、评分和浏览量保持不变。

| 标识 | 名称 / 分类 | 游玩入口 | 完整署名 / 来源链接 |
| --- | --- | --- | --- |
| `birdland` | BIRDLAND / `romance` 恋爱 | [英文原版游戏本体](https://birdland.camp/) | Brendan Patrick Hennessy / Izzy Marbella；[官方作品页](https://bphennessy.itch.io/birdland) |

入口直接打开单款游戏自身的开始页，作品介绍页只用于作者及出处，不作为游玩地址。
沿现有 `external` 链路：目录 API → 游戏卡片 → 新标签打开原版。作者榜沿既有主作者及完整署名搜索规则，未增加别名或改动作者算法。
中文简介说明夏令营、少女 Bridget 对 Bell 的感情和奇幻梦境，并标明英文及粗口 / 成熟话题；不声称中文支持、全年龄或完整汉化授权。

## 正式封面与公开署名

文件：`covers/birdland.jpg`，900×900 RGB JPEG，**211,272 B**，宽高比 **1**。
正式目标为 [CDN 封面](https://img.pingxingxian.space/static/web/catalog/2026-11-05-v4/covers/birdland.jpg)，类型 `image/jpeg`。
画面为真实鸟群、落日与粉红天空，非纯标题或平台截图。

- © **Brendan Patrick Hennessy**，作者于 **2015-10-01** 上传至 IFDB。
- [原图](https://ifdb.org/showimage?id=0%3A722) / [IFDB 素材及授权记录](https://ifdb.org/viewgame?coverart=&id=ap1651hvjldbuugj&ldesc=)。
- 依据 [Creative Commons Attribution 3.0 United States（CC BY 3.0 US）](https://creativecommons.org/licenses/by/3.0/us/) 使用。
- 原图扩展名虽被临时存为 PNG，实际编码为 JPEG；最终仅使用正确 `.jpg` 文件名，保留原始字节和元数据，未重编码、缩放、裁切或加字。卡片按现有容器显示。
- 无损 WebP 对照为 **830,088 B**，大于原 JPEG，未采用；不为统一格式重复有损编码。仓库优化脚本仅支持 PNG / WebP，不把 JPEG 写成已通过该脚本。比较及实看记录位于本批可视化 `assets/delivery.json`。
- 公开 [封面署名页](https://pingxingxian.space/licenses/catalog-covers.html) 随前端发布，目录页脚提供 `封面署名` 入口，包含作者、原图、来源、许可证、加工说明及范围限制。

**上述许可只适用于该封面，不覆盖游戏正文、程序或 Izzy Marbella 的其他插画，也不代表获得汉化 / 游戏包再分发许可。**

## 同批交付与数据语义

- `0107_add_birdland.py` 只追加一条，前置 `0106_add_direct_game_sites`，无 DDL。
- 分类必须已经存在；先检查固定 slug 和入口有无末尾斜线，包含隐藏、跨分类记录，有匹配则不覆盖或重复收录。
- 排序追加至包含隐藏记录的分类末尾；新记录默认浏览量零，不创建评分。回退版本不删除业务记录，需撤下时走管理员隐藏入口。
- 正式图片、`coverManifest.ts`、真实 `coverAspectManifest.ts`、上传清单、公开署名页及目录页脚同批。
- 不变更旧封面、默认裁切、作者归并、分页、懒加载、缓存规则或工作流，不增加依赖。

## 验证与发布记录

- 迁移独立内存 SQLite **13 项通过**，覆盖新增、幂等、跨分类 / 隐藏 / 尾斜线去重、人工资料 / 评分 / 浏览量保持、缺分类和非破坏性回退；Python 语法与 Ruff 通过。该证据不代替真实 MySQL 升级。
- 前端类型检查、上传脚本语法 / Ruff、唯一 v4 key、JPEG 解码及旧 SVG / WebP 类型保持检查通过。
- 生产预检：schema `0106_add_direct_game_sites`；恋爱分类存在、公开零款、原有一条隐藏记录；BIRDLAND 标识 / 地址含隐藏无重复；全站公开 **230**。
- 原十二款及上批三款共十五条完整资料、浏览量、原评分及关联 AI 记录已只读留存；九款隐藏状态不变。
- 发布前源代码 / Web 镜像为 `cbd1b4653d79a6c4fe3072a83497943529c4d773`，API / Web 健康，六服务运行。

- 本地 Playwright 两端 **2 passed（8.1s）**：发现页 / 恋爱分类 / 搜索正式封面、精确游玩链接及新标签安全属性、一次本地统计夹具、旧封面、九隐藏、完整作者 / Izzy 搜索均通过。实际从目录页脚打开许可 HTML，返回 200，署名 / 来源 / 许可 / 范围正确，无横向溢出或页面异常；本地服务器已停止。
- 两端实际图像已检查，鸟群和夕阳清楚。手机窄卡会正常裁去图内标题顶缘，但卡片名称完整，不是缺图；未改变全局裁切或添加图中文字。
- 新 v4 对象上传前不存在；仅上传这一张并存储回读校验。公开 GET **200 image/jpeg**，900×900 / 211,272 B，与本地字节一致且解码成功；未覆盖旧对象或全局清缓存。

限定提交推送、同 SHA 流水线与真实生产数据 / 页面结果，完成后补记于本节，不以上传成功或本地检查替代上线验收。

## 恢复

本批恢复目录：`/data/releases/birdland-20261105-01a1a966/`，保存发布前源提交、十五条数据 / 评分、旧镜像和 `recover.sh`；已检查新文件无服务器未跟踪冲突及恢复脚本语法。
恢复仅使用已固定的 API / worker / Web 旧镜像；API 跳过 Alembic 启动以免旧代码无法识别新迁移版本。
不自动删除新条目、降级数据或还原数据库。旧 Web 若需同步撤下新条目，应使用另获授权的管理员隐藏操作，保留原记录、评分及浏览量。
健康检查为 `curl -fsS --connect-timeout 5 --max-time 20 https://pingxingxian.space/healthz`。
