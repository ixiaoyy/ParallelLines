import assert from "node:assert/strict";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { renderBirdland } from "./build-birdland.mjs";

const sourceRoot = new URL("../game-sources/birdland/", import.meta.url);
const original = fs.readFileSync(new URL("birdland_en.html", sourceRoot), "utf8");
const imageMap = JSON.parse(fs.readFileSync(new URL("image-map.json", sourceRoot), "utf8"));
const { html } = renderBirdland();
const cdnPrefix = "https://img.pingxingxian.space/static/web/games/birdland/2026-11-05-v1/";

function decode(value) {
  return value.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}

function passages(document) {
  return [...document.matchAll(/<tw-passagedata pid="(\d+)" name="([^"]+)" tags="([^"]*)" position="([^"]*)">([\s\S]*?)<\/tw-passagedata>/g)]
    .map(([, pid, name, tags, position, body]) => ({ pid, name, tags, position, body: decode(body) }));
}

function targets(body) {
  const links = [...body.matchAll(/\[\[([^\]]+)\]\]/g)].map(([, inner]) => {
    if (inner.includes("<-")) return `link:${inner.split("<-")[0].trim()}`;
    if (inner.includes("|")) return `link:${inner.split("|")[1].trim()}`;
    return `link:${inner.trim()}`;
  });
  const displays = [...body.matchAll(/display\(\s*["']([^"']+)["']\s*\)/g)].map(([, target]) => `display:${target}`);
  const moods = [...body.matchAll(/(serenity|alacrity|tenacity|vigilance|melancholy|guile)link\(\s*(["'])(?:\\.|(?!\2)[^\\])*\2\s*,\s*["']([^"']+)["']\s*,\s*(\d+)\s*\)/g)]
    .map(([, kind, , target, level]) => `mood:${kind}:${target}:${level}`);
  return [...links, ...displays, ...moods].sort();
}

test("927 个段落标识、剧情跳转与条件链接保留，全部模板可编译", () => {
  const before = passages(original);
  const after = passages(html);
  assert.equal(after.length, 927);
  assert.deepEqual(after.map((entry) => [entry.pid, entry.name, entry.tags, entry.position]),
    before.map((entry) => [entry.pid, entry.name, entry.tags, entry.position]));
  const names = new Set(after.map((passage) => passage.name));
  for (let index = 0; index < after.length; index++) {
    const passage = after[index];
    assert.deepEqual(targets(passage.body), targets(before[index].body), passage.name);
    for (const target of targets(passage.body)) {
      const destination = target.startsWith("mood:") ? target.split(":")[2] : target.slice(target.indexOf(":") + 1);
      assert(names.has(destination), `${passage.name} -> ${destination}`);
    }
    let code = "";
    for (const [, expression, statement] of passage.body.matchAll(/<%(=?)([\s\S]*?)%>/g)) {
      code += expression ? `void (${statement});\n` : `${statement}\n`;
    }
    assert.doesNotThrow(() => new Function(code), passage.name);
  }
});

test("20 张图片全部指向版本化 CDN，无本地 PNG 或 Base64 回退", () => {
  assert.equal(Object.keys(imageMap).length, 20);
  assert.equal(new Set([...html.matchAll(/https:\/\/img\.pingxingxian\.space\/static\/web\/games\/birdland\/2026-11-05-v1\/[\w.-]+\.webp/g)].map(([url]) => url)).size, 20);
  for (const filename of Object.values(imageMap)) assert(html.includes(`${cdnPrefix}${filename}`));
  assert(!html.includes("img/"));
  assert(!html.includes("data:image/png;base64,"));
  assert(!html.includes("d:/work/"));
});

test("生成入口可复现，并保留原存档键、原作者、中文菜单及手机 viewport", () => {
  const output = fileURLToPath(new URL("../public/games/birdland/index.html", import.meta.url));
  assert.equal(fs.readFileSync(output, "utf8"), html);
  assert(html.includes("birdlandautosave"));
  assert(html.includes("Brendan Patrick Hennessy"));
  assert(html.includes("Izzy Marbella"));
  assert(html.includes("开始游戏"));
  assert(html.includes('lang="zh-CN"'));
  assert(html.includes('name="viewport" content="width=device-width,initial-scale=1"'));
  assert(!html.includes("#passage{font-size:70%}"));
});

test("显式预览地址仅改图片前缀，非法地址被拒绝", () => {
  const preview = renderBirdland({ assetBaseUrl: "http://127.0.0.1:8765/static/web/" }).html;
  assert.equal(preview, html.replaceAll("https://img.pingxingxian.space/static/web", "http://127.0.0.1:8765/static/web"));
  assert.throws(() => renderBirdland({ assetBaseUrl: "javascript:alert(1)" }));
});
