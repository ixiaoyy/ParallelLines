export interface ComposerEmojiOption {
  label: string;
  value: string;
  preview: string;
  description: string;
}

export interface CodeLanguageOption {
  label: string;
  value: string;
}

export interface OneboxPreview {
  id: string;
  url: string;
  host: string;
  title: string;
  summary: string;
  initial: string;
}

export interface ComposerCodeBlock {
  index: number;
  language: string;
  code: string;
}

export interface ComposerPreview {
  html: string;
  oneboxes: OneboxPreview[];
  codeBlocks: ComposerCodeBlock[];
  characterCount: number;
}

const URL_PATTERN = /\bhttps?:\/\/[^\s<>"')\]]+/gi;
const FILE_URL_PATTERN = /\.(?:png|jpe?g|gif|webp|svg|pdf|zip|rar|7z|tar|gz|mp4|mov|webm|mp3|wav)(?:[?#].*)?$/i;
const LANGUAGE_PATTERN = /^[a-z0-9_+#.-]{1,24}$/i;

export const COMPOSER_EMOJI_OPTIONS: ComposerEmojiOption[] = [
  { label: "平行线", value: ":parallel:", preview: "〽️", description: "项目自定义表情" },
  { label: "已解决", value: ":solved:", preview: "✅", description: "标记方案有效" },
  { label: "复现", value: ":repro:", preview: "🔁", description: "可复现问题" },
  { label: "赞", value: "👍", preview: "👍", description: "表达赞同" },
  { label: "感谢", value: "🙏", preview: "🙏", description: "表达感谢" },
  { label: "灵感", value: "💡", preview: "💡", description: "补充思路" },
  { label: "警告", value: "⚠️", preview: "⚠️", description: "提醒风险" },
  { label: "代码", value: "🧩", preview: "🧩", description: "代码片段" },
];

export const CODE_LANGUAGE_OPTIONS: CodeLanguageOption[] = [
  { label: "TypeScript", value: "ts" },
  { label: "JavaScript", value: "js" },
  { label: "Python", value: "py" },
  { label: "SQL", value: "sql" },
  { label: "Shell", value: "sh" },
  { label: "JSON", value: "json" },
  { label: "HTML", value: "html" },
  { label: "CSS/SCSS", value: "scss" },
  { label: "纯文本", value: "text" },
];

const CUSTOM_EMOJI_BY_CODE = new Map(
  COMPOSER_EMOJI_OPTIONS.filter((option) => option.value.startsWith(":")).map((option) => [
    option.value,
    option.preview,
  ]),
);

export function buildComposerPreview(rawMd: string): ComposerPreview {
  const trimmed = rawMd.trim();
  const codeBlocks: ComposerCodeBlock[] = [];

  return {
    html: trimmed ? renderMarkdown(trimmed, codeBlocks) : "",
    oneboxes: detectOneboxes(trimmed),
    codeBlocks,
    characterCount: rawMd.length,
  };
}

function renderMarkdown(rawMd: string, codeBlocks: ComposerCodeBlock[]): string {
  const lines = rawMd.replace(/\r\n?/g, "\n").split("\n");
  const html: string[] = [];
  let paragraph: string[] = [];
  let list: string[] = [];
  let quote: string[] = [];
  let code: string[] = [];
  let inCodeFence = false;
  let codeLanguage = "text";

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${renderInline(paragraph.join("\n"))}</p>`);
    paragraph = [];
  };

  const flushList = () => {
    if (!list.length) return;
    html.push(`<ul>${list.map((item) => `<li>${renderInline(item)}</li>`).join("")}</ul>`);
    list = [];
  };

  const flushQuote = () => {
    if (!quote.length) return;
    html.push(`<blockquote>${quote.map((line) => renderInline(line)).join("<br />")}</blockquote>`);
    quote = [];
  };

  const flushTextBlocks = () => {
    flushParagraph();
    flushList();
    flushQuote();
  };

  const flushCode = () => {
    const safeLanguage = normalizeLanguage(codeLanguage);
    const codeText = code.join("\n");
    const index = codeBlocks.length;
    codeBlocks.push({ index, language: safeLanguage, code: codeText });
    html.push(
      `<pre data-lang="${escapeAttribute(safeLanguage)}" data-code-index="${index}"><code class="language-${escapeAttribute(
        safeLanguage,
      )}">${escapeHtml(codeText)}</code></pre>`,
    );
    code = [];
    codeLanguage = "text";
  };

  for (const line of lines) {
    const fence = line.match(/^```\s*([^\s`]*)\s*$/);
    if (fence) {
      if (inCodeFence) {
        flushCode();
        inCodeFence = false;
      } else {
        flushTextBlocks();
        inCodeFence = true;
        codeLanguage = fence[1] || "text";
      }
      continue;
    }

    if (inCodeFence) {
      code.push(line);
      continue;
    }

    if (!line.trim()) {
      flushTextBlocks();
      continue;
    }

    const quoteMatch = line.match(/^>\s?(.*)$/);
    if (quoteMatch) {
      flushParagraph();
      flushList();
      quote.push(quoteMatch[1]);
      continue;
    }

    const listMatch = line.match(/^\s*(?:[-*+]|\d+\.)\s+(.+)$/);
    if (listMatch) {
      flushParagraph();
      flushQuote();
      list.push(listMatch[1]);
      continue;
    }

    flushList();
    flushQuote();
    paragraph.push(line);
  }

  if (inCodeFence) {
    flushCode();
  }
  flushTextBlocks();

  return html.join("");
}

function renderInline(raw: string): string {
  let html = escapeHtml(raw);

  for (const [shortcode, emoji] of CUSTOM_EMOJI_BY_CODE.entries()) {
    html = html.replaceAll(escapeHtml(shortcode), `<span class="composer-custom-emoji">${emoji}</span>`);
  }

  html = html.replace(
    /!\[([^\]\n]*)\]\((https?:\/\/[^)\s]+|\/[^)\s]+)\)/g,
    (_match, alt: string, src: string) =>
      `<img src="${escapeAttribute(src)}" alt="${escapeAttribute(alt)}" loading="lazy" />`,
  );
  html = html.replace(
    /\[([^\]\n]+)\]\((https?:\/\/[^)\s]+|\/[^)\s]+)\)/g,
    (_match, label: string, href: string) =>
      `<a href="${escapeAttribute(href)}" target="_blank" rel="noopener noreferrer">${label}</a>`,
  );
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>");

  return html;
}

function detectOneboxes(rawMd: string): OneboxPreview[] {
  const seen = new Set<string>();
  const previews: OneboxPreview[] = [];

  for (const match of rawMd.matchAll(URL_PATTERN)) {
    const url = trimUrl(match[0]);
    if (seen.has(url) || FILE_URL_PATTERN.test(url)) {
      continue;
    }

    try {
      const parsed = new URL(url);
      const host = parsed.hostname.replace(/^www\./, "");
      const pathTitle = parsed.pathname
        .split("/")
        .filter(Boolean)
        .slice(-2)
        .join(" / ")
        .replace(/[-_]+/g, " ");

      seen.add(url);
      previews.push({
        id: `${host}-${previews.length}`,
        url,
        host,
        title: pathTitle ? `${host} · ${pathTitle}` : host,
        summary: "已自动生成安全链接预览；如站点无法抓取元数据，将保留此降级摘要。",
        initial: (host[0] ?? "链").toUpperCase(),
      });
    } catch {
      // Ignore malformed URLs in drafts.
    }
  }

  return previews.slice(0, 4);
}

function trimUrl(url: string): string {
  return url.replace(/[.,;:!?]+$/g, "");
}

function normalizeLanguage(language: string): string {
  const value = language.trim().toLowerCase();
  if (!value || !LANGUAGE_PATTERN.test(value)) {
    return "text";
  }
  return value;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeAttribute(value: string): string {
  return escapeHtml(value).replace(/`/g, "&#96;");
}
