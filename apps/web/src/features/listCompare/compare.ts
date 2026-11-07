/** 单份名单的原文长度上限，避免一次粘贴过大的表格把页面卡住。 */
export const LIST_COMPARE_MAX_CHARS = 1_000_000;

/** 去掉空行后的条数上限。超过后要求分段，不在页面里截断。 */
export const LIST_COMPARE_MAX_ENTRIES = 20_000;

/**
 * 示例同时覆盖中文姓名、重复项、空行、首尾空格、带前导零的编号，以及英文大小写。
 * 名单 A 中的「  001」用来展示首尾空格会被清掉，中间的空行会被忽略。
 */
export const SAMPLE_LIST_A = "张三\n李四\n  001\n王五\n张三\n\nAlice\n1";
export const SAMPLE_LIST_B = "李四\n王五\n002\n赵六\n001\nalice";

export interface CompareOptions {
  dedupe: boolean;
  ignoreCase: boolean;
}

export interface ListSummary {
  /** 去掉空行并清理首尾空格后的原文，顺序与输入一致。 */
  entries: string[];
  blankLines: number;
  /** 按当前选项整理后的条目。未开启去重时与 entries 内容相同。 */
  prepared: string[];
  removedDuplicates: number;
}

export interface CompareInput extends CompareOptions {
  listA: string;
  listB: string;
}

export interface CompareSuccess {
  ok: true;
  both: string[];
  onlyA: string[];
  onlyB: string[];
  blankA: number;
  blankB: number;
  countA: number;
  countB: number;
  removedA: number;
  removedB: number;
}

export type CompareFailure =
  | { ok: false; reason: "empty"; side: "A" | "B" | "both" }
  | { ok: false; reason: "too-many"; side: "A" | "B"; count: number; limit: number }
  | { ok: false; reason: "too-large"; side: "A" | "B" };

export type CompareResult = CompareSuccess | CompareFailure;

/**
 * 只折叠英文 A–Z。中文、数字和带前导零的编号保持原样，也不做全角转换。
 * 这样「001」和「1」、「张三」和带空格的「张 三」都不会被悄悄当成同一条。
 */
export function comparisonKey(text: string, ignoreCase: boolean): string {
  if (!ignoreCase) return text;
  return text.replace(/[A-Z]/g, (letter) => String.fromCharCode(letter.charCodeAt(0) + 32));
}

/** 复制到剪贴板的文本。使用 CRLF，粘回 Excel 时每一条会落到单独的单元格。 */
export function toClipboardText(lines: readonly string[]): string {
  return lines.join("\r\n");
}

/** 下载文件在正文前加 UTF-8 BOM，让 Windows 记事本按中文打开。 */
export function toDownloadText(lines: readonly string[]): string {
  return `\uFEFF${toClipboardText(lines)}`;
}

/**
 * 把文本框内容整理成名单。
 * 浏览器粘贴 Excel 单列后，换行一般是 LF；这里同时接受 CRLF 和旧式 CR。
 * 末尾单独的换行是 Excel 复制时常见的结束符，不记成一条空记录。
 */
export function summarizeList(source: string, options: CompareOptions): ListSummary {
  const parsed = parseEntries(source);
  const prepared = options.dedupe ? dedupeEntries(parsed.entries, options.ignoreCase) : parsed.entries.slice();
  return {
    entries: parsed.entries,
    blankLines: parsed.blankLines,
    prepared,
    removedDuplicates: parsed.entries.length - prepared.length,
  };
}

/** 对照两份已整理名单。数据只在调用方内存中计算，不读取网络。 */
export function compareNameLists(input: CompareInput): CompareResult {
  if (input.listA.length > LIST_COMPARE_MAX_CHARS) return { ok: false, reason: "too-large", side: "A" };
  if (input.listB.length > LIST_COMPARE_MAX_CHARS) return { ok: false, reason: "too-large", side: "B" };

  const options: CompareOptions = { dedupe: input.dedupe, ignoreCase: input.ignoreCase };
  const summaryA = summarizeList(input.listA, options);
  const summaryB = summarizeList(input.listB, options);
  if (summaryA.entries.length > LIST_COMPARE_MAX_ENTRIES) {
    return { ok: false, reason: "too-many", side: "A", count: summaryA.entries.length, limit: LIST_COMPARE_MAX_ENTRIES };
  }
  if (summaryB.entries.length > LIST_COMPARE_MAX_ENTRIES) {
    return { ok: false, reason: "too-many", side: "B", count: summaryB.entries.length, limit: LIST_COMPARE_MAX_ENTRIES };
  }
  if (summaryA.entries.length === 0 && summaryB.entries.length === 0) return { ok: false, reason: "empty", side: "both" };
  if (summaryA.entries.length === 0) return { ok: false, reason: "empty", side: "A" };
  if (summaryB.entries.length === 0) return { ok: false, reason: "empty", side: "B" };

  const groups = diffEntries(summaryA.prepared, summaryB.prepared, input.ignoreCase);
  return {
    ok: true,
    ...groups,
    blankA: summaryA.blankLines,
    blankB: summaryB.blankLines,
    countA: summaryA.prepared.length,
    countB: summaryB.prepared.length,
    removedA: summaryA.removedDuplicates,
    removedB: summaryB.removedDuplicates,
  };
}

/** 把失败原因写成页面上直接展示的句子。 */
export function explainCompareFailure(failure: CompareFailure): string {
  if (failure.reason === "too-large") {
    const wan = LIST_COMPARE_MAX_CHARS / 10_000;
    return `名单 ${failure.side} 超过 ${wan} 万个字符，请分段粘贴后再核对。`;
  }
  if (failure.reason === "too-many") {
    return `名单 ${failure.side} 共有 ${failure.count} 条，单次最多核对 ${failure.limit} 条。请分段后再试。`;
  }
  if (failure.side === "both") return "名单 A 和名单 B 都还没有内容。请各输入至少一条，或点击「填入示例」。";
  return `名单 ${failure.side} 还没有可核对的内容。空行和只有空格的行会忽略，请至少输入一条。`;
}

function parseEntries(source: string): { entries: string[]; blankLines: number } {
  if (source.length === 0) return { entries: [], blankLines: 0 };
  const lines = source.split(/\r\n|\n|\r/);
  if (lines[lines.length - 1] === "") lines.pop();
  const entries: string[] = [];
  let blankLines = 0;
  for (const line of lines) {
    const text = line.trim();
    if (text.length === 0) {
      blankLines += 1;
      continue;
    }
    entries.push(text);
  }
  return { entries, blankLines };
}

/** 去重保留第一次出现的原文，顺序不变。忽略大小写时按英文折叠后的键判断重复。 */
function dedupeEntries(entries: readonly string[], ignoreCase: boolean): string[] {
  const seen = new Set<string>();
  const prepared: string[] = [];
  for (const text of entries) {
    const key = comparisonKey(text, ignoreCase);
    if (seen.has(key)) continue;
    seen.add(key);
    prepared.push(text);
  }
  return prepared;
}

/**
 * 按出现次数配对，而不是只看“有没有”。
 * A 有 2 次、B 有 1 次时，1 次进入两边都有，多出的 1 次留在仅 A 有。
 * 两边都有和仅 A 有沿用 A 的顺序与写法；仅 B 有沿用 B 的顺序与写法。
 */
function diffEntries(left: readonly string[], right: readonly string[], ignoreCase: boolean): Pick<CompareSuccess, "both" | "onlyA" | "onlyB"> {
  const rightCounts = countEntries(right, ignoreCase);
  const leftCounts = countEntries(left, ignoreCase);
  const both: string[] = [];
  const onlyA: string[] = [];
  for (const text of left) {
    const key = comparisonKey(text, ignoreCase);
    const remaining = rightCounts.get(key) ?? 0;
    if (remaining > 0) {
      both.push(text);
      rightCounts.set(key, remaining - 1);
    } else {
      onlyA.push(text);
    }
  }
  const onlyB: string[] = [];
  for (const text of right) {
    const key = comparisonKey(text, ignoreCase);
    const remaining = leftCounts.get(key) ?? 0;
    if (remaining > 0) leftCounts.set(key, remaining - 1);
    else onlyB.push(text);
  }
  return { both, onlyA, onlyB };
}

function countEntries(entries: readonly string[], ignoreCase: boolean): Map<string, number> {
  const counts = new Map<string, number>();
  for (const text of entries) {
    const key = comparisonKey(text, ignoreCase);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}
