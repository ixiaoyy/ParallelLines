import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = fileURLToPath(new URL("../", import.meta.url));
const sourceRoot = path.join(webRoot, "game-sources/birdland");
const outputPath = path.join(webRoot, "public/games/birdland/index.html");
const imagePrefix = "/games/birdland/2026-11-05-v1";
const defaultAssetBase = "https://img.pingxingxian.space/static/web";
const passagePattern = /<tw-passagedata pid="(\d+)" name="([^"]+)" tags="([^"]*)" position="([^"]*)">([\s\S]*?)<\/tw-passagedata>/g;

/** 将译文字符串编码为 HTML 实体字符串，供 Twine 数据节点读取；不改剧情与脚本。 */
function escapeHtml(value) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/** 从归档原版与译文返回 HTML、段落数和图片数，不写磁盘；assetBaseUrl 为 CDN 或显式预览 HTTP(S) 前缀。 */
export function renderBirdland({ assetBaseUrl = process.env.VITE_STATIC_ASSET_BASE_URL || defaultAssetBase } = {}) {
  const assetBase = assetBaseUrl.trim().replace(/\/+$/, "");
  if (!/^https?:\/\/[^\s"'<>]+$/.test(assetBase)) {
    throw new Error("Birdland asset base must be an absolute HTTP(S) URL");
  }
  const imageMap = JSON.parse(fs.readFileSync(path.join(sourceRoot, "image-map.json"), "utf8"));
  const passages = new Map();
  // 译文逐段覆盖原数据，缺段与重复必须中止，避免发布半汉化版本。
  for (let part = 1; part <= 62; part++) {
    const filename = `part_${String(part).padStart(2, "0")}_zh.json`;
    const translated = JSON.parse(fs.readFileSync(path.join(sourceRoot, "translations", filename), "utf8"));
    for (const [id, entry] of Object.entries(translated)) {
      const body = typeof entry === "string" ? entry : entry.body;
      if (passages.has(id) || typeof body !== "string") throw new Error(`Invalid or duplicate passage ${id}`);
      passages.set(id, body);
    }
  }
  if (passages.size !== 927) throw new Error(`Expected 927 passages, received ${passages.size}`);

  let html = fs.readFileSync(path.join(sourceRoot, "birdland_en.html"), "utf8");
  html = html.replace("<html>", '<html lang="zh-CN">')
    .replace("<title>BIRDLAND</title>", "<title>BIRDLAND · 鸟之国度（中文汉化版）</title>")
    .replace("<meta charset=utf-8>", '<meta charset=utf-8><meta name="viewport" content="width=device-width,initial-scale=1">')
    .replace("A young adult text game about falling in love, coming to terms with who you are, and saving your entire summer camp from weird alien bird monsters.",
      "一部关于坠入爱河、认清自我，以及从怪异的外星鸟类怪物手中拯救整个夏令营的青春互动小说。")
    .replace('font-family:"Georgia",serif;', 'font-family:"Songti SC","Noto Serif SC","Source Han Serif SC","STSong","Georgia","PingFang SC","Microsoft YaHei",serif;\n\tline-height:175%;')
    .replace('font-family:"Century Gothic","Verdana",sans-serif;', 'font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Century Gothic","Verdana",sans-serif;')
    .replace(".dream a {\n\tcolor:#CF1020;trans\n}", ".dream a {\n\tcolor:#CF1020;\n}")
    // 已有真实 viewport，移除旧桌面画布缩放补丁，保留手机正文 12pt 的原响应式规则。
    .replace("@media screen and (max-device-width:480px){#passage{font-size:70%}}", "")
    // 菜单按完整条目换行，避免中文在手机上从词中间断开，并保留可点按高度。
    .replace("#menu a {\n\tcolor:white;\n}", "#menu a {\n\tcolor:white;\n\tdisplay:inline-block;\n\tmin-height:44px;\n\twhite-space:nowrap;\n}")
    // 极窄屏保持头像原尺寸并居中，避免浮动把中文正文挤成几字一行。
    .replace('</style><script role="script"', '@media screen and (max-width:360px){.sidebox{float:none;margin:0 auto 1em;}}</style><script role="script"')
    .replace('return "<ul><li class=\'next\'>[[Next|"+target+"]]</li></ul>"',
      'return "<ul><li class=\'next\'>[[继续|"+target+"]]</li></ul>"')
    .replace('moodtext = ["Impossibly Lowered", "Very Lowered", "Lowered", "Normal", "Heightened", "Very Heightened", "🔒 Very Heightened"]',
      'moodtext = ["极度低落", "非常低落", "略微低落", "正常", "高涨", "非常高涨", "🔒 非常高涨"]');
  const stats = { SERENITY: "平静", ALACRITY: "机敏", TENACITY: "坚韧", VIGILANCE: "警觉", MELANCHOLY: "忧郁", GUILE: "诡诈" };
  for (const [english, chinese] of Object.entries(stats)) {
    for (const kind of ["freestat", "blockedstat"]) {
      html = html.replaceAll(`<span class='${kind}'>${english}</span>`, `<span class='${kind}'>${chinese}</span>`);
    }
  }
  let replaced = 0;
  html = html.replace(passagePattern, (_match, id, name, tags, position) => {
    if (!passages.has(id)) throw new Error(`Missing passage ${id} (${name})`);
    replaced++;
    return `<tw-passagedata pid="${id}" name="${name}" tags="${tags}" position="${position}">${escapeHtml(passages.get(id))}</tw-passagedata>`;
  });
  if (replaced !== passages.size) throw new Error(`Replaced ${replaced} of ${passages.size} passages`);

  // 标题、预载和正文动态显示共用同一份版本化 CDN 图片，不内嵌 Base64 或回退本地 PNG。
  const usedImages = new Set();
  html = html.replace(/img\/([a-zA-Z0-9_.-]+\.png)/g, (_match, filename) => {
    const selected = imageMap[filename];
    if (!selected || !/^[a-zA-Z0-9_.-]+\.webp$/.test(selected)) throw new Error(`Missing optimized image ${filename}`);
    const localAsset = path.resolve(webRoot, "../../static/web", `.${imagePrefix}`, selected);
    if (!fs.existsSync(localAsset)) throw new Error(`Missing CDN source ${localAsset}`);
    usedImages.add(filename);
    return `${assetBase}${imagePrefix}/${selected}`;
  });
  if (usedImages.size !== Object.keys(imageMap).length) throw new Error("Unused image manifest entry");
  return { html, passageCount: replaced, imageCount: usedImages.size };
}

// 生成文件随源码入库，普通 Vite 构建无需本机路径、额外下载或预先执行此脚本。
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { html, passageCount, imageCount } = renderBirdland();
  if (process.argv.includes("--check")) {
    if (fs.readFileSync(outputPath, "utf8") !== html) throw new Error("Birdland generated entry is stale");
  } else {
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, html, "utf8");
  }
  console.log(`Birdland: ${passageCount} passages, ${imageCount} CDN images, ${Buffer.byteLength(html)} bytes`);
}
