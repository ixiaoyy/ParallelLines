import { describe, expect, it, vi } from "vitest";
import { SSF } from "xlsx";
import { formulaLessons, practiceSheets } from "./content";
import expandedPractice from "./expandedPractice.json";
import { createTrialSheets, FormulaTrialError, type TrialRequest } from "./formulaTrial";
import { calculateFormulaTrial } from "./formulaTrialEngine";
import { formatTrialValue } from "./formulaTrialFormat";

function request(id = "person-total", formula?: string): TrialRequest {
  const lesson = formulaLessons.find((item) => item.id === id)!;
  return { formula: formula ?? lesson.formula, sheetName: lesson.sheetName, targetCell: lesson.targetCell,
    sheets: createTrialSheets(practiceSheets) };
}
/** 每个负例都必须实际失败，不能因未进入 catch 而被当成通过。 */
function expectFailure(data: unknown, code: string): void {
  let failure: unknown;
  try { calculateFormulaTrial(data); } catch (error) { failure = error; }
  expect(failure).toBeInstanceOf(FormulaTrialError);
  expect(failure).toMatchObject({ code });
}

describe("50 篇教程使用真实离线引擎试算", () => {
  it.each(formulaLessons.map((lesson) => [lesson.id, lesson] as const))("%s 与原教材答案一致", (id, lesson) => {
    const result = calculateFormulaTrial(request(id));
    const format = expandedPractice.exercises.find((exercise) => exercise.id === id)?.numberFormat;
    if (lesson.expectedValues) expect(result.values.flat()).toEqual(lesson.expectedValues);
    else expect(formatTrialValue(result.values[0]![0]!, format)).toBe(lesson.expected);
  });

  it("修改真实输入会改变结果，固定 D 列答案与日期显示缓存不参与计算", () => {
    const data = request();
    data.sheets.find((sheet) => sheet.name === "数据")!.rows[1]![3] = 500;
    data.sheets.find((sheet) => sheet.name === "练习")!.rows[2]![3] = "不应读取的缓存答案";
    expect(calculateFormulaTrial(data).values).toEqual([[650]]);
    expect(data.sheets.find((sheet) => sheet.name === "练习")!.rows[2]![3]).toBe("不应读取的缓存答案");
  });

  it("公式本身可修改，错误不冒充 0 或原教材结果", () => {
    expect(calculateFormulaTrial(request("person-total", "=1+2*3")).values).toEqual([[7]]);
    expectFailure(request("person-total", "=1/0"), "#DIV/0!");
  });

  it("日期序号不受上海历史时区偏移影响，按月计算保留月末规则", () => {
    expect(calculateFormulaTrial(request("person-total", "=DATE(2026,1,5)")).values).toEqual([[46027]]);
    expect(calculateFormulaTrial(request("person-total", "=DAY(DATE(2026,1,5))")).values).toEqual([[5]]);
    expect(calculateFormulaTrial(request("person-total", "=TEXT(EDATE(DATE(2026,1,31),1),\"yyyy-mm-dd\")")).values).toEqual([["2026-02-28"]]);
    expect(calculateFormulaTrial(request("person-total", "=DAY(60)")).values).toEqual([[29]]);
  });

  it.each([
    ["=WEBSERVICE(\"https://example.invalid\")", "UNSUPPORTED"], ["=INDIRECT(\"C3\")", "UNSUPPORTED"],
    ["=SUM(A:A)", "UNSUPPORTED"], ["=SUM(A1:A999999)", "LIMIT"], ["=unknownName", "INVALID"],
    ["=C3", "CYCLE"], ["=SUM(C2:C4)", "CYCLE"], ["=IFERROR(C3,0)", "CYCLE"],
    ["='外部表'!A1", "#REF!"], ["='[book.xlsx]Sheet1'!A1", "UNSUPPORTED"],
  ])("拒绝不允许的写法或资源：%s", (formula, code) => {
    expectFailure(request("person-total", formula), code);
  });

  it("函数/引用大小写可规范，字符串中的函数样文字不作为代码", () => {
    expect(calculateFormulaTrial(request("person-total", "=sum('数据'!d2:d5)")).values).toEqual([[750]]);
    expect(calculateFormulaTrial(request("person-total", '=LEN("SUM(A1)")')).values).toEqual([[7]]);
    expect(calculateFormulaTrial(request("person-total", '=TRUE')).values).toEqual([[true]]);
  });

  it("IFNA 只接住未找到，不能吞掉除零", () => {
    expect(calculateFormulaTrial(request("missing-lookup")).values).toEqual([["未找到"]]);
    expect(calculateFormulaTrial(request("person-total", '=IFNA(IF(TRUE,VLOOKUP("absent",\'名单\'!A2:C4,3,FALSE),"unused"),"fallback")')).values).toEqual([["fallback"]]);
    expectFailure(request("person-total", '=IFNA(1/0,"fallback")'), "#DIV/0!");
  });

  it("IFERROR 只处理 Excel 计算错误，不能把能力/资源守卫转成成功的零", () => {
    expectFailure(request("person-total", '=IFERROR(SORT(\'办公数据\'!D2:D7,1,-1,TRUE),0)'), "UNSUPPORTED");
    expectFailure(request("person-total", '=IFERROR(XLOOKUP(B3,\'名单\'!A2:A4,\'名单\'!C2:C4,0,2),0)'), "UNSUPPORTED");
    expectFailure(request("person-total", '=IFERROR(COUNTIFS(\'数据\'!A2:A5,"*****************"),0)'), "UNSUPPORTED");
    expect(calculateFormulaTrial(request("person-total", '=IFERROR(1/0,"fallback")')).values).toEqual([["fallback"]]);
    expect(calculateFormulaTrial(request("missing-lookup", '=IFERROR(VLOOKUP(B25,\'名单\'!A2:C4,3,FALSE),"fallback")')).values).toEqual([["fallback"]]);
  });

  it("IFERROR 不吞底层实现异常，也不把原始异常输出到结果", () => {
    const formatter = vi.spyOn(SSF, "format").mockImplementation(() => { throw new Error("private internal fixture"); });
    try { expectFailure(request("person-total", '=IFERROR(TEXT(10,"0"),0)'), "INVALID"); }
    finally { formatter.mockRestore(); }
  });

  it("布尔字面量在 IF 和比较中保留类型，不改字符串或文本单元格", () => {
    for (const [formula, value] of [
      ["=IF(1=1,TRUE,FALSE)", true], ["=IF(1=2,TRUE,FALSE)", false],
      ["=IF(AND(TRUE,NOT(FALSE)),IF(TRUE,FALSE,TRUE),TRUE)", false],
      ["=TRUE=1", false], ["=FALSE=0", false], ["=TRUE<>1", true], ['=IF(TRUE,"FALSE","TRUE")', "FALSE"],
    ] as const) expect(calculateFormulaTrial(request("person-total", formula)).values).toEqual([[value]]);
    const trial = request("person-total", "=B3");
    trial.sheets.find((sheet) => sheet.name === "练习")!.rows[2]![1] = "TRUE";
    expect(calculateFormulaTrial(trial).values).toEqual([["TRUE"]]);
    expectFailure(request("person-total", "=PLBOOLTRUE()"), "UNSUPPORTED");
  });

  it("平均无匹配报错，COUNTIFS星号只匹配文本，转义星号按字面匹配", () => {
    const trial = request("person-total", '=COUNTIFS(\'数据\'!A2:A7,"*")');
    const data = trial.sheets.find((sheet) => sheet.name === "数据")!;
    data.rows = [["值"], [""], [0], [false], ["A"], ["12"], ["*"]];
    expect(calculateFormulaTrial(trial).values).toEqual([[3]]);
    trial.formula = '=COUNTIFS(\'数据\'!A2:A7,"~*")';
    expect(calculateFormulaTrial(trial).values).toEqual([[1]]);
    expectFailure(request("person-total", '=AVERAGEIFS(\'数据\'!D2:D5,\'数据\'!C2:C5,"不存在")'), "#DIV/0!");
  });

  it("UNIQUE按完整行去重，SORT按数字而非字典序，不能覆盖非空邻格", () => {
    const trial = request("unique-employees", '=UNIQUE(\'数据\'!A2:B5)');
    trial.sheets.find((sheet) => sheet.name === "数据")!.rows = [["编号", "数值"], ["A", 120], ["A", 80], ["A", 120], ["B", 300]];
    expect(calculateFormulaTrial(trial).values).toEqual([["A", 120], ["A", 80], ["B", 300]]);
    trial.formula = '=SORT(\'数据\'!B2:B5,1,-1)';
    expect(calculateFormulaTrial(trial).values).toEqual([[300], [120], [120], [80]]);
    trial.formula = '=UNIQUE(\'数据\'!A2:B5)';
    trial.sheets.find((sheet) => sheet.name === trial.sheetName)!.rows[1]![1] = "不可覆盖";
    expectFailure(trial, "SPILL");
  });

  it("超长公式、非法日期与异常消息形状明确失败，不把日期样工号转换成日期", () => {
    expect(() => calculateFormulaTrial(request("person-total", `=${"1+".repeat(3000)}1`))).toThrow(FormulaTrialError);
    expect(() => calculateFormulaTrial({ formula: "=1", sheets: [null] })).toThrow(FormulaTrialError);
    const trial = request("right-phone");
    trial.sheets.find((sheet) => sheet.name === "练习")!.rows[29]![1] = "2026-01-05";
    expect(calculateFormulaTrial(trial).values).toEqual([["1-05"]]);
    const invalid = request("next-month");
    invalid.sheets.find((sheet) => sheet.name === "办公数据")!.rows[1]![4] = "2026-02-31";
    expectFailure(invalid, "DATE");
  });
});
