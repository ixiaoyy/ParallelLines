import { describe, expect, it } from "vitest";

import {
  LIST_COMPARE_MAX_CHARS,
  LIST_COMPARE_MAX_ENTRIES,
  SAMPLE_LIST_A,
  SAMPLE_LIST_B,
  compareNameLists,
  comparisonKey,
  explainCompareFailure,
  summarizeList,
  toClipboardText,
  toDownloadText,
  type CompareOptions,
} from "./compare";

const exact: CompareOptions = { dedupe: false, ignoreCase: false };
const deduped: CompareOptions = { dedupe: true, ignoreCase: false };
const folded: CompareOptions = { dedupe: false, ignoreCase: true };

describe("名单整理", () => {
  it("清理首尾空格、忽略空行，并保留中文、内部空格和前导零", () => {
    const summary = summarizeList(" \t001 \u00a0\r\n\u3000张三\u3000\r\n\r\n张 三\r\n\r\n", exact);
    expect(summary.entries).toEqual(["001", "张三", "张 三"]);
    expect(summary.blankLines).toBe(2);
    expect(summary.prepared).toEqual(summary.entries);
    expect(summary.removedDuplicates).toBe(0);
  });

  it("Excel 单列末尾换行不记为空记录，单元格内的制表符不拆列", () => {
    expect(summarizeList("001\r\n张三\r\n", exact).entries).toEqual(["001", "张三"]);
    expect(summarizeList("001\r\n张三\r\n", exact).blankLines).toBe(0);
    expect(summarizeList("张三\t销售部", exact).entries).toEqual(["张三\t销售部"]);
    expect(summarizeList("李四\r王五", exact).entries).toEqual(["李四", "王五"]);
  });

  it("空文本和只有空格的文本都没有可核对条目", () => {
    expect(summarizeList("", exact)).toMatchObject({ entries: [], blankLines: 0 });
    expect(summarizeList("   \n\t\n", exact)).toMatchObject({ entries: [], blankLines: 2 });
    expect(summarizeList("0", exact).entries).toEqual(["0"]);
  });

  it("去重保留第一次出现的原文和顺序", () => {
    const summary = summarizeList("张三\n李四\n张三\n  张三  ", deduped);
    expect(summary.entries).toEqual(["张三", "李四", "张三", "张三"]);
    expect(summary.prepared).toEqual(["张三", "李四"]);
    expect(summary.removedDuplicates).toBe(2);
  });

  it("忽略大小写只折叠英文 A 到 Z", () => {
    expect(comparisonKey("AbC张三001", true)).toBe("abc张三001");
    expect(comparisonKey("ＩＤ", true)).toBe("ＩＤ");
    const summary = summarizeList("Alice\nalice\nALICE\nBob", { dedupe: true, ignoreCase: true });
    expect(summary.prepared).toEqual(["Alice", "Bob"]);
  });
});

describe("两份名单核对", () => {
  it("示例数据保留重复中文姓名、空行清理结果和带前导零的编号", () => {
    const result = compareNameLists({ listA: SAMPLE_LIST_A, listB: SAMPLE_LIST_B, ...exact });
    expect(result).toMatchObject({
      ok: true,
      both: ["李四", "001", "王五"],
      onlyA: ["张三", "张三", "Alice", "1"],
      onlyB: ["002", "赵六", "alice"],
      blankA: 1,
      blankB: 0,
      countA: 7,
      countB: 6,
      removedA: 0,
      removedB: 0,
    });
  });

  it("重复项按次数配对，顺序沿用各自原始名单", () => {
    const result = compareNameLists({ listA: "甲\n甲\n乙", listB: "甲\n丙\n甲", ...exact });
    expect(result).toMatchObject({ ok: true, both: ["甲", "甲"], onlyA: ["乙"], onlyB: ["丙"] });
    const once = compareNameLists({ listA: "甲\n甲\n乙", listB: "甲", ...exact });
    expect(once).toMatchObject({ ok: true, both: ["甲"], onlyA: ["甲", "乙"], onlyB: [] });
  });

  it("001、1 和 1.0 不会被当成同一个编号", () => {
    const result = compareNameLists({ listA: "001\n1\n1.0\n001", listB: "001\n1", ...exact });
    expect(result).toMatchObject({ ok: true, both: ["001", "1"], onlyA: ["1.0", "001"], onlyB: [] });
  });

  it("去重后再按次数核对，仍保留第一次出现的写法", () => {
    const result = compareNameLists({ listA: SAMPLE_LIST_A, listB: SAMPLE_LIST_B, ...deduped });
    expect(result).toMatchObject({
      ok: true,
      both: ["李四", "001", "王五"],
      onlyA: ["张三", "Alice", "1"],
      onlyB: ["002", "赵六", "alice"],
      removedA: 1,
      countA: 6,
    });
  });

  it("忽略英文大小写时两边都有保留名单 A 的写法", () => {
    const result = compareNameLists({ listA: "Alice\n张三", listB: "alice\nALICE", ...folded });
    expect(result).toMatchObject({ ok: true, both: ["Alice"], onlyA: ["张三"], onlyB: ["ALICE"] });
    const sample = compareNameLists({ listA: SAMPLE_LIST_A, listB: SAMPLE_LIST_B, ...folded });
    expect(sample).toMatchObject({
      ok: true,
      both: ["李四", "001", "王五", "Alice"],
      onlyA: ["张三", "张三", "1"],
      onlyB: ["002", "赵六"],
    });
  });

  it("去重和忽略大小写可以同时使用", () => {
    const result = compareNameLists({
      listA: "Alice\nalice\nBob",
      listB: "BOB\nbob",
      dedupe: true,
      ignoreCase: true,
    });
    expect(result).toMatchObject({ ok: true, both: ["Bob"], onlyA: ["Alice"], onlyB: [], removedB: 1 });
  });

  it("连续核对不会受到上一次次数扣减的影响", () => {
    const input = { listA: "甲\n甲", listB: "甲", ...exact };
    expect(compareNameLists(input)).toEqual(compareNameLists(input));
  });

  it("任一侧没有有效内容时给出明确原因", () => {
    expect(compareNameLists({ listA: " \n", listB: "", ...exact })).toMatchObject({ ok: false, reason: "empty", side: "both" });
    expect(compareNameLists({ listA: "", listB: "李四", ...exact })).toMatchObject({ ok: false, reason: "empty", side: "A" });
    expect(compareNameLists({ listA: "张三", listB: " \t", ...exact })).toMatchObject({ ok: false, reason: "empty", side: "B" });
    expect(explainCompareFailure({ ok: false, reason: "empty", side: "both" })).toContain("填入示例");
    expect(explainCompareFailure({ ok: false, reason: "empty", side: "A" })).toContain("名单 A");
  });

  it("超过条数或字数上限时拒绝核对，不截断结果", () => {
    const tooMany = Array.from({ length: LIST_COMPARE_MAX_ENTRIES + 1 }, () => "张三").join("\n");
    const many = compareNameLists({ listA: tooMany, listB: "张三", ...exact });
    expect(many).toMatchObject({ ok: false, reason: "too-many", side: "A", count: LIST_COMPARE_MAX_ENTRIES + 1 });
    const tooLarge = compareNameLists({ listA: "张三", listB: "李".repeat(LIST_COMPARE_MAX_CHARS + 1), ...exact });
    expect(tooLarge).toMatchObject({ ok: false, reason: "too-large", side: "B" });
    expect(explainCompareFailure({ ok: false, reason: "too-many", side: "A", count: 3, limit: 2 })).toBe(
      "名单 A 共有 3 条，单次最多核对 2 条。请分段后再试。",
    );
  });
});

describe("结果文本", () => {
  it("复制和下载保持条目顺序，下载文件带 BOM，且不额外增加空行", () => {
    expect(toClipboardText(["张三", "001"])).toBe("张三\r\n001");
    expect(toDownloadText(["张三", "001"])).toBe("\uFEFF张三\r\n001");
    expect(toClipboardText(["001"])).toBe("001");
  });
});
