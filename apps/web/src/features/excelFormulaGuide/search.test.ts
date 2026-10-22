import { describe, expect, it } from "vitest";

import { formulaLessons } from "./content";
import { matchesLessonSearch } from "./search";

/** 使用实际教程数据检查搜索结果，预期按办公任务语义独立给出。 */
function matchingIds(query: string): string[] {
  return formulaLessons.filter((lesson) => matchesLessonSearch(lesson, query)).map((lesson) => lesson.id);
}

describe("Excel 教程搜索", () => {
  it.each([
    ["按人员汇总", "person-total"],
    ["查找重复项", "duplicate-id"],
    ["核对提交名单", "missing-submissions"],
  ])("页面搜索示例可以找到对应教程：%s", (query, expectedId) => {
    expect(matchingIds(query)).toEqual([expectedId]);
  });
  it.each(["怎么算一个人的总金额", "怎么计算同一个人的总金额", "请问怎么计算同一个人的总金额？"])("人员汇总问句：%s", (query) => {
    expect(matchingIds(query)).toEqual(["person-total"]);
  });

  it.each(["找出重复的人", "查重", "找出重复的工号"])("查重问句：%s", (query) => {
    expect(matchingIds(query)).toEqual(["duplicate-id"]);
  });

  it.each(["找出不重复的人", "去重", "名单去重", "生成不重复的工号名单"])("不重复和去重不混入重复结果：%s", (query) => {
    expect(matchingIds(query)).toEqual(["unique-employees"]);
  });

  it.each(["把手机号后四位取出来", "请问手机号后4位怎么用"])("提取手机后四位：%s", (query) => {
    expect(matchingIds(query)).toEqual(["right-phone"]);
  });

  it.each(["两个条件同时满足", "全部条件满足", "多个条件都满足"])("所有条件满足：%s", (query) => {
    expect(matchingIds(query)).toEqual(["and-conditions"]);
  });

  it.each(["只要满足其中一个条件", "任一条件满足", "至少一个条件满足"])("任意一个条件满足：%s", (query) => {
    expect(matchingIds(query)).toEqual(["or-conditions"]);
  });

  it("只归一函数名标点，保留现有函数名和多关键词的搜索结果", () => {
    const baseline = matchingIds("sumifs");
    expect(baseline).toContain("person-total");
    expect(baseline).toContain("department-status-total");
    expect(matchingIds("SUMIFS(")).toEqual(baseline);
    expect(matchingIds("ＳＵＭＩＦＳ（）")).toEqual(baseline);
    expect(matchingIds("sumifs 金额")).toEqual(matchingIds("SUMIFS（），金额"));
    expect(matchingIds("按人 汇总")).toContain("person-total");
    expect(matchingIds("SUMIFS 不存在的条件")).toEqual([]);
  });

  it("礼貌前后缀不要求用户掌握函数写法", () => {
    expect(matchingIds("请问 SUMIFS 金额 怎么用")).toEqual(matchingIds("SUMIFS 金额"));
    expect(matchingIds("SUMIFS怎么用")).toEqual(matchingIds("SUMIFS"));
  });

  it("未覆盖的问题不被猜成近似业务需求", () => {
    expect(matchingIds("把手机号前四位取出来")).not.toContain("right-phone");
    expect(matchingIds("把手机号后六位取出来")).not.toContain("right-phone");
    expect(matchingIds("一个人的平均金额怎么算")).not.toContain("person-total");
    expect(matchingIds("部门和状态同时满足时汇总金额")).not.toContain("and-conditions");
    expect(matchingIds("不需要同时满足全部条件")).not.toContain("and-conditions");
    expect(matchingIds("排除一个人的总金额")).not.toContain("person-total");
    expect(matchingIds("删除重复的人")).not.toContain("duplicate-id");
    expect(matchingIds("隐藏手机号后四位")).not.toContain("right-phone");
    expect(matchingIds("将手机号后四位替换成星号")).not.toContain("right-phone");
    expect(matchingIds("不计算每个人总金额")).not.toContain("person-total");
    expect(matchingIds("只计算每个人总金额大于1000的记录")).not.toContain("person-total");
    expect(matchingIds("今天晚饭吃什么")).toEqual([]);
  });

  it.each(["&", "<>", "=", "+", "-", "*", "/", "%"])("有意义的运算符不能被清成空输入：%s", (query) => {
    expect(matchingIds(query).length).toBeLessThan(50);
  });

  it("多关键词的否定语义不能被别名覆盖，空输入仍显示全部", () => {
    expect(matchingIds("名单 去重")).not.toContain("duplicate-id");
    expect(matchingIds("不重复 不存在的条件")).toEqual([]);
    expect(matchingIds("")).toHaveLength(50);
    expect(matchingIds(" \n\t ")).toHaveLength(50);
  });
});
