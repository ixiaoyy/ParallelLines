import { expect, test, type BrowserContext } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";

// 固定的扩充验收清单独立于生产数据，防止缺教程、错位置或错误示例被自证通过。
const expandedCases =
[
  {
    "id": "average-amount",
    "title": "算出平均每笔金额",
    "targetCell": "C12",
    "expected": "150",
    "formula": "=AVERAGE('办公数据'!D2:D7)"
  },
  {
    "id": "maximum-amount",
    "title": "找出最大的一笔金额",
    "targetCell": "C13",
    "expected": "300",
    "formula": "=MAX('办公数据'!D2:D7)"
  },
  {
    "id": "minimum-amount",
    "title": "找出最小的一笔金额",
    "targetCell": "C14",
    "expected": "50",
    "formula": "=MIN('办公数据'!D2:D7)"
  },
  {
    "id": "count-numbers",
    "title": "数一列里有多少个数字",
    "targetCell": "C15",
    "expected": "6",
    "formula": "=COUNT('办公数据'!D2:D7)"
  },
  {
    "id": "count-nonempty",
    "title": "数一列有多少个非空单元格",
    "targetCell": "C16",
    "expected": "6",
    "formula": "=COUNTA('办公数据'!B2:B7)"
  },
  {
    "id": "count-blanks",
    "title": "检查有多少个目标数没有填写",
    "targetCell": "C17",
    "expected": "1",
    "formula": "=COUNTBLANK('办公数据'!H2:H7)"
  },
  {
    "id": "average-by-department",
    "title": "只计算某个部门的平均金额",
    "targetCell": "C18",
    "expected": "125",
    "formula": "=AVERAGEIFS('办公数据'!D2:D7,'办公数据'!C2:C7,B18)"
  },
  {
    "id": "subtotal-visible",
    "title": "只合计筛选后看得见的金额",
    "targetCell": "C19",
    "expected": "900",
    "formula": "=SUBTOTAL(109,'办公数据'!D2:D7)"
  },
  {
    "id": "percent-of-total",
    "title": "计算一笔金额占总金额的比例",
    "targetCell": "C20",
    "expected": "13.33%",
    "formula": "='办公数据'!D2/SUM('办公数据'!D2:D7)"
  },
  {
    "id": "and-conditions",
    "title": "两个条件都满足才显示符合",
    "targetCell": "C21",
    "expected": "符合",
    "formula": "=IF(AND('办公数据'!G2>=8,'办公数据'!F2=\"已完成\"),\"符合\",\"不符合\")"
  },
  {
    "id": "or-conditions",
    "title": "满足任意一个条件就需要通知",
    "targetCell": "C22",
    "expected": "需通知",
    "formula": "=IF(OR('办公数据'!C2=\"行政\",'办公数据'!C2=\"人事\"),\"需通知\",\"无需通知\")"
  },
  {
    "id": "not-status",
    "title": "把尚未完成的记录标成待跟进",
    "targetCell": "C23",
    "expected": "已完成",
    "formula": "=IF(NOT('办公数据'!F2=\"已完成\"),\"待跟进\",\"已完成\")"
  },
  {
    "id": "blank-check",
    "title": "没有填写时显示待填写",
    "targetCell": "C24",
    "expected": "待填写",
    "formula": "=IF(B24=\"\",\"待填写\",\"已填写\")"
  },
  {
    "id": "missing-lookup",
    "title": "查不到工号时显示未找到",
    "targetCell": "C25",
    "expected": "未找到",
    "formula": "=IFNA(VLOOKUP(B25,'名单'!$A$2:$C$4,3,FALSE),\"未找到\")"
  },
  {
    "id": "safe-division",
    "title": "计算出错时给出检查提示",
    "targetCell": "C26",
    "expected": "检查原始数据",
    "formula": "=IFERROR(120/B26,\"检查原始数据\")"
  },
  {
    "id": "index-match",
    "title": "按姓名向左查出工号",
    "targetCell": "C27",
    "expected": "U002",
    "formula": "=INDEX('名单'!A2:A4,MATCH(B27,'名单'!B2:B4,0))"
  },
  {
    "id": "xlookup-department",
    "title": "用新版公式按工号查部门",
    "targetCell": "C28",
    "expected": "行政",
    "formula": "=XLOOKUP(B28,'名单'!A2:A4,'名单'!C2:C4,\"未找到\")"
  },
  {
    "id": "left-code",
    "title": "提取编号开头的两个字母",
    "targetCell": "C29",
    "expected": "XS",
    "formula": "=LEFT(B29,2)"
  },
  {
    "id": "right-phone",
    "title": "提取手机号的后四位",
    "targetCell": "C30",
    "expected": "8000",
    "formula": "=RIGHT(B30,4)"
  },
  {
    "id": "mid-code",
    "title": "提取编号中间的年份",
    "targetCell": "C31",
    "expected": "2026",
    "formula": "=MID(B31,4,4)"
  },
  {
    "id": "text-length",
    "title": "检查一段文字有多少个字符",
    "targetCell": "C32",
    "expected": "6",
    "formula": "=LEN(B32)"
  },
  {
    "id": "find-separator",
    "title": "找出编号中第一个横线的位置",
    "targetCell": "C33",
    "expected": "3",
    "formula": "=FIND(\"-\",B33)"
  },
  {
    "id": "replace-label",
    "title": "把文字中的旧部门替换成新部门",
    "targetCell": "C34",
    "expected": "行政部-张三",
    "formula": "=SUBSTITUTE(B34,\"旧部门\",\"行政部\")"
  },
  {
    "id": "combine-fields",
    "title": "把姓名和部门合并到一个格子",
    "targetCell": "C35",
    "expected": "张三 / 行政",
    "formula": "='名单'!B2&\" / \"&'名单'!C2"
  },
  {
    "id": "join-roster",
    "title": "把多个人名合并成一行",
    "targetCell": "C36",
    "expected": "张三、李四、王五",
    "formula": "=TEXTJOIN(\"、\",TRUE,'名单'!B2:B4)"
  },
  {
    "id": "format-month",
    "title": "把日期显示成年月文字",
    "targetCell": "C37",
    "expected": "2026-01",
    "formula": "=TEXT(DATE(2026,1,5),\"yyyy-mm\")"
  },
  {
    "id": "date-interval",
    "title": "计算两个日期之间相差几天",
    "targetCell": "C38",
    "expected": "3",
    "formula": "='办公数据'!E3-'办公数据'!E2"
  },
  {
    "id": "extract-dateparts",
    "title": "从日期提取年月日",
    "targetCell": "C39",
    "expected": "2026年1月5日",
    "formula": "=YEAR('办公数据'!E2)&\"年\"&MONTH('办公数据'!E2)&\"月\"&DAY('办公数据'!E2)&\"日\""
  },
  {
    "id": "next-month",
    "title": "计算一个月之后的日期",
    "targetCell": "C40",
    "expected": "2026-02-05",
    "formula": "=EDATE('办公数据'!E2,1)"
  },
  {
    "id": "workdays",
    "title": "计算两个日期间的工作日",
    "targetCell": "C41",
    "expected": "5",
    "formula": "=NETWORKDAYS(DATE(2026,1,5),DATE(2026,1,9))"
  },
  {
    "id": "overdue",
    "title": "按指定核对日判断是否到期",
    "targetCell": "C42",
    "expected": "已到期",
    "formula": "=IF('办公数据'!E2<DATE(2026,1,10),\"已到期\",\"未到期\")"
  },
  {
    "id": "month-total",
    "title": "只汇总某个月的金额",
    "targetCell": "C43",
    "expected": "400",
    "formula": "=SUMIFS('办公数据'!D2:D7,'办公数据'!E2:E7,\">=\"&DATE(2026,1,1),'办公数据'!E2:E7,\"<\"&DATE(2026,2,1))"
  },
  {
    "id": "round-up",
    "title": "有小数时向上取到整数",
    "targetCell": "C44",
    "expected": "13",
    "formula": "=ROUNDUP(B44,0)"
  },
  {
    "id": "round-down",
    "title": "直接去掉小数部分",
    "targetCell": "C45",
    "expected": "12",
    "formula": "=ROUNDDOWN(B45,0)"
  },
  {
    "id": "integer-round",
    "title": "理解负数向下取整的结果",
    "targetCell": "C46",
    "expected": "-13",
    "formula": "=INT(B46)"
  },
  {
    "id": "rank-amount",
    "title": "给一笔金额排个名次",
    "targetCell": "C47",
    "expected": "4",
    "formula": "=RANK.EQ('办公数据'!D2,'办公数据'!$D$2:$D$7,0)"
  },
  {
    "id": "top-amount",
    "title": "找出第二大的金额",
    "targetCell": "C48",
    "expected": "200",
    "formula": "=LARGE('办公数据'!D2:D7,B48)"
  },
  {
    "id": "filter-completed",
    "title": "自动列出已完成记录中的姓名",
    "targetCell": "A2",
    "expected": "张三、李四、王五、赵六（纵向 4 行）",
    "formula": "=FILTER('办公数据'!B2:B7,'办公数据'!F2:F7=\"已完成\",\"无符合记录\")"
  },
  {
    "id": "unique-employees",
    "title": "生成不重复的工号名单",
    "targetCell": "A2",
    "expected": "U001、U002、U003、U004（纵向 4 行）",
    "formula": "=UNIQUE('办公数据'!A2:A7)"
  },
  {
    "id": "sort-amounts",
    "title": "把金额自动从大到小排列",
    "targetCell": "A2",
    "expected": "300、200、150、120、80、50（纵向 6 行）",
    "formula": "=SORT('办公数据'!D2:D7,1,-1)"
  }
]
;

/** 保留真实页面和练习文件；所有接口和站外请求在浏览器侧拦截，避免访问统计写入。 */
async function isolateLocalGuide(context: BrowserContext) {
  const origin = new URL(baseURL).origin;
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith("/api/")) {
      await route.fulfill({ json: { data: null } });
    } else if (url.origin !== origin) {
      await route.abort();
    } else {
      await route.continue();
    }
  });
}

test.beforeEach(async ({ context }) => {
  await isolateLocalGuide(context);
});

test("手机分享和刷新教程时定位正文，普通入口及后退保留正确阅读位置", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/tools/excel-formulas?lesson=person-total");
  const heading = page.getByRole("heading", { name: "同一个人有多笔，算他的总金额", exact: true });
  await expect(heading).toBeInViewport();
  await page.reload();
  await expect(heading).toBeInViewport();

  // 历史记录的恢复优先于首次进入定位，返回页面时不把已经读到的位置改回标题。
  await page.getByTestId("formula-recipe").scrollIntoViewIfNeeded();
  const readingPosition = await page.evaluate(() => window.scrollY);
  await page.evaluate(() => document.querySelector<HTMLAnchorElement>(".formula-back-link")?.click());
  await expect(page).toHaveURL(/\/tools$/);
  await page.goBack();
  await expect.poll(async () => Math.abs(await page.evaluate(() => window.scrollY) - readingPosition)).toBeLessThan(4);

  await page.goto("/tools/excel-formulas");
  await expect(page.getByRole("heading", { name: "Excel 公式速查", exact: true })).toBeInViewport();
  const directory = page.getByRole("navigation", { name: "公式教程目录" });
  await expect(directory.getByRole("button")).toHaveCount(50);
  const list = directory.locator(".formula-lessons");
  expect(await list.evaluate((element) => element.clientHeight)).toBeLessThan(500);
  // 收起列表高度后，最后一项仍可真实点击，不能用裁切隐藏教程。
  await directory.getByRole("button").filter({ hasText: "把金额自动从大到小排列" }).click();
  await expect(page.getByRole("heading", { name: "把金额自动从大到小排列", exact: true })).toBeInViewport();
});

test("日常完整问句和函数括号可搜索，保留否定及条件之间的区别", async ({ page }) => {
  await page.goto("/tools/excel-formulas");
  const search = page.getByRole("searchbox", { name: "搜索教程" });
  const directory = page.getByRole("navigation", { name: "公式教程目录" });
  const cases = [
    ["按人员汇总", "同一个人有多笔，算他的总金额", "按工号找到这个人的部门"],
    ["查找重复项", "找出重复出现的姓名或工号", "生成不重复的工号名单"],
    ["核对提交名单", "对比名单，找出谁还没交材料", "找出重复出现的姓名或工号"],
    ["怎么算一个人的总金额", "同一个人有多笔，算他的总金额", "按工号找到这个人的部门"],
    ["怎么计算同一个人的总金额", "同一个人有多笔，算他的总金额", "按工号找到这个人的部门"],
    ["找出重复的人", "找出重复出现的姓名或工号", "生成不重复的工号名单"],
    ["找出不重复的人", "生成不重复的工号名单", "找出重复出现的姓名或工号"],
    ["把手机号后四位取出来", "提取手机号的后四位", "提取编号开头的两个字母"],
    ["两个条件同时满足", "两个条件都满足才显示符合", "满足任意一个条件就需要通知"],
    ["只要满足其中一个条件", "满足任意一个条件就需要通知", "两个条件都满足才显示符合"],
  ];
  for (const [query, included, excluded] of cases) {
    await search.fill(query!);
    await expect(directory.getByRole("button").filter({ hasText: included! })).toHaveCount(1);
    await expect(directory.getByRole("button").filter({ hasText: excluded! })).toHaveCount(0);
  }
  for (const query of ["SUMIFS(", "ＳＵＭＩＦＳ（）", "按人 汇总"]) {
    await search.fill(query);
    await expect(directory.getByRole("button").filter({ hasText: "同一个人有多笔，算他的总金额" })).toHaveCount(1);
  }
  for (const [query, excluded] of [
    ["隐藏手机号后四位", "提取手机号的后四位"],
    ["将手机号后四位替换成星号", "提取手机号的后四位"],
    ["不计算每个人总金额", "同一个人有多笔，算他的总金额"],
    ["只计算每个人总金额大于1000的记录", "同一个人有多笔，算他的总金额"],
  ]) {
    await search.fill(query!);
    await expect(directory.getByRole("button").filter({ hasText: excluded! })).toHaveCount(0);
  }
});

test("从工具入口进入完整教程，五十篇教程可定位且保留公式、步骤与正确结果", async ({ page }) => {
  test.setTimeout(90_000);
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto("/tools");
  await page.getByRole("link", { name: "打开工具" }).click();
  await expect(page).toHaveURL(/\/tools\/excel-formulas/);
  await expect(page.getByRole("heading", { name: "Excel 公式速查", exact: true })).toBeVisible();

  // 原十篇与新增四十篇分别按已确认的练习位置检查，保留旧链接和原示例。
  const lessons = [
    ["total-amount", "C2", "750", "SUM("],
    ["person-total", "C3", "250", "SUMIFS("],
    ["department-status-total", "C4", "400", "SUMIFS("],
    ["condition-count", "C5", "2", "COUNTIFS("],
    ["employee-lookup", "C6", "财务", "VLOOKUP("],
    ["missing-submissions", "C7", "未提交", "COUNTIFS("],
    ["duplicate-id", "C8", "重复", "COUNTIFS("],
    ["target-check", "C9", "未达标", "IF("],
    ["trim-name", "C10", "张三", "TRIM("],
    ["round-amount", "C11", "12.35", "ROUND("],
    ...expandedCases.map((lesson) => [lesson.id, lesson.targetCell, lesson.expected, lesson.formula]),
  ];
  for (const [id, cell, expected, formula] of lessons) {
    await page.goto(`/tools/excel-formulas?lesson=${id}`);
    const article = page.getByTestId("lesson-content");
    await expect(article).toBeVisible();
    await expect(article).toContainText(cell!);
    await expect(page.getByTestId("lesson-formula")).toContainText(formula!);
    await expect(page.getByTestId("expected-result")).toContainText(expected!);
    expect(await page.getByTestId("lesson-steps").getByRole("listitem").count()).toBeGreaterThanOrEqual(5);
    await expect(article.locator('a[href^="https://support.microsoft.com/"]').first()).toBeVisible();
  }
  expect(pageErrors).toEqual([]);
});

test("大白话搜索、多词搜索、无结果恢复与教程刷新定位", async ({ page }) => {
  await page.goto("/tools/excel-formulas");
  const search = page.getByRole("searchbox", { name: "搜索教程" });
  const directory = page.getByRole("navigation", { name: "公式教程目录" });
  await search.fill("按人");
  await expect(directory).toContainText("同一个人");
  await search.fill("SUMIFS 金额");
  await expect(directory).toContainText("金额");
  await search.fill("不存在的教程关键词");
  await expect(page.getByText("没有找到相关教程，换个说法试试。")).toBeVisible();
  await search.fill("");
  await expect(directory.getByRole("button")).toHaveCount(50);
  await directory.getByRole("button").filter({ hasText: "按工号找到这个人的部门" }).click();
  await expect(page).toHaveURL(/lesson=employee-lookup/);
  await page.reload();
  await expect(page.getByTestId("lesson-formula")).toContainText("VLOOKUP(");
  await page.goto("/tools/excel-formulas?lesson=not-a-lesson");
  await expect(page.getByTestId("lesson-formula")).toContainText("SUM(");
});

test("复制真实公式、复制失败可手动选择，并能下载真实练习工作簿", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async (value: string) => { document.documentElement.dataset.copiedFormula = value; } },
    });
  });
  await page.goto("/tools/excel-formulas?lesson=person-total");
  const formula = await page.getByTestId("lesson-formula").textContent();
  await page.getByRole("button", { name: "复制公式", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("已复制");
  expect(await page.evaluate(() => document.documentElement.dataset.copiedFormula)).toBe(formula);
  await page.evaluate(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async () => { throw new Error("clipboard unavailable in test"); } },
    });
  });
  await page.getByRole("button", { name: /复制/ }).click();
  await expect(page.getByText("复制失败，请选中公式手动复制。")).toBeVisible();
  await expect(page.getByTestId("lesson-formula")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "下载练习表", exact: true }).first().click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("excel-formula-practice.xlsx");
  expect(await download.failure()).toBeNull();
  const response = await page.request.get("/tools/excel-formulas/excel-formula-practice.xlsx");
  expect(response.status()).toBe(200);
  // 开发服务器可能不标注 xlsx 类型，实际下载仍须是完整的工作簿 ZIP。
  const bytes = await response.body();
  expect(bytes.subarray(0, 2).toString()).toBe("PK");
  expect(bytes.length).toBeGreaterThan(2000);
});

test("手机和桌面正文可读，长公式不撑宽页面，键盘可进入独立工具", async ({ page }) => {
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/tools/excel-formulas?lesson=department-status-total");
    await expect(page.getByTestId("lesson-content")).toBeVisible();
    await expect(page.getByTestId("lesson-formula")).toContainText("SUMIFS(");
    await page.getByRole("navigation", { name: "公式教程目录" }).getByRole("button").filter({ hasText: "同一个人" }).click();
    await expect(page.getByRole("heading", { name: "同一个人有多笔，算他的总金额", exact: true })).toBeInViewport();
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
  }
  await page.goto("/tools");
  const launch = page.getByRole("link", { name: "打开工具" });
  await launch.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/tools\/excel-formulas/);
});

test("按想得到的结果选课，八类任务覆盖五十篇教程并清除旧筛选", async ({ page }) => {
  await page.goto("/tools/excel-formulas");
  const search = page.getByRole("searchbox", { name: "搜索教程" });
  const categories = page.getByRole("group", { name: "教程分类" });
  const directory = page.getByRole("navigation", { name: "公式教程目录" });

  // 预期来自用户要解决的工作任务，不读取页面内的数据结构作为答案。
  const tasks = [
  {
    "title": "算金额、平均数和占比",
    "lessons": [
      "把这一列金额全部加起来",
      "同一个人有多笔，算他的总金额",
      "只计算某个部门已完成的金额",
      "算出平均每笔金额",
      "找出最大的一笔金额",
      "找出最小的一笔金额",
      "只计算某个部门的平均金额",
      "只合计筛选后看得见的金额",
      "计算一笔金额占总金额的比例",
      "只汇总某个月的金额"
    ]
  },
  {
    "title": "数记录条数",
    "lessons": [
      "数一数有多少条记录符合条件",
      "数一列里有多少个数字",
      "数一列有多少个非空单元格",
      "检查有多少个目标数没有填写"
    ]
  },
  {
    "title": "查人员资料",
    "lessons": [
      "按工号找到这个人的部门",
      "查不到工号时显示未找到",
      "按姓名向左查出工号",
      "用新版公式按工号查部门"
    ]
  },
  {
    "title": "核对漏交或重复人员",
    "lessons": [
      "对比名单，找出谁还没交材料",
      "找出重复出现的姓名或工号",
      "生成不重复的工号名单"
    ]
  },
  {
    "title": "判断条件是否满足",
    "lessons": [
      "判断有没有达到目标",
      "两个条件都满足才显示符合",
      "满足任意一个条件就需要通知",
      "把尚未完成的记录标成待跟进",
      "没有填写时显示待填写",
      "计算出错时给出检查提示",
      "按指定核对日判断是否到期"
    ]
  },
  {
    "title": "处理文字和数字",
    "lessons": [
      "去掉名字前后的多余空格",
      "把金额四舍五入到两位小数",
      "提取编号开头的两个字母",
      "提取手机号的后四位",
      "提取编号中间的年份",
      "检查一段文字有多少个字符",
      "找出编号中第一个横线的位置",
      "把文字中的旧部门替换成新部门",
      "把姓名和部门合并到一个格子",
      "把多个人名合并成一行",
      "有小数时向上取到整数",
      "直接去掉小数部分",
      "理解负数向下取整的结果"
    ]
  },
  {
    "title": "计算日期和工作日",
    "lessons": [
      "把日期显示成年月文字",
      "计算两个日期之间相差几天",
      "从日期提取年月日",
      "计算一个月之后的日期",
      "计算两个日期间的工作日"
    ]
  },
  {
    "title": "筛选、排序和排名",
    "lessons": [
      "给一笔金额排个名次",
      "找出第二大的金额",
      "自动列出已完成记录中的姓名",
      "把金额自动从大到小排列"
    ]
  }
];
  const observedLessons = new Set<string>();
  for (const task of tasks) {
    await search.fill("不存在的任务检索");
    await categories.getByRole("button", { name: "文字与数字", exact: true }).click();
    await page.getByRole("button", { name: task.title, exact: true }).click();
    await expect(search).toHaveValue("");
    await expect(categories.getByRole("button", { name: "文字与数字", exact: true })).toHaveAttribute("aria-pressed", "false");
    await expect(directory.getByRole("button")).toHaveCount(task.lessons.length);
    for (const title of task.lessons) {
      await expect(directory.getByRole("button").filter({ hasText: title })).toHaveCount(1);
    }
    for (const title of await directory.getByRole("button").allTextContents()) observedLessons.add(title.trim());
    if (task.lessons.length === 1) {
      await expect(page.getByRole("heading", { name: task.lessons[0]!, exact: true })).toBeInViewport();
    } else {
      const recommendations = page.getByTestId("task-recommendations");
      await expect(recommendations).toBeVisible();
      for (const title of task.lessons) await expect(recommendations).toContainText(title);
    }
    if (task.title === "算金额、平均数和占比") {
      const recommendations = page.getByTestId("task-recommendations");
      await expect(recommendations).toContainText("指定一个工号，把这个人的多笔金额全部加在一起。");
      await expect(recommendations).toContainText("部门和状态两个条件都满足，才把这一行金额算进去。");
      await recommendations.getByRole("button").filter({ hasText: "同一个人有多笔" }).click();
      await expect(page).toHaveURL(/lesson=person-total/);
      await expect(page.getByRole("heading", { name: "同一个人有多笔，算他的总金额", exact: true })).toBeInViewport();
    }
  }
  expect(observedLessons.size).toBe(50);
  await categories.getByRole("button", { name: "全部", exact: true }).click();
  await expect(directory.getByRole("button")).toHaveCount(50);

  // 手机从任务进入对应场景，选择后直接定位正文，不在长目录里继续寻找。
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/tools/excel-formulas");
    await page.getByRole("button", { name: "查人员资料", exact: true }).click();
    await page.getByTestId("task-recommendations").getByRole("button").filter({ hasText: "按工号找到这个人的部门" }).click();
    await expect(page).toHaveURL(/lesson=employee-lookup/);
    await expect(page.getByRole("heading", { name: "按工号找到这个人的部门", exact: true })).toBeInViewport();
    await expect(directory.getByRole("button")).toHaveCount(4);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
});

test("易混用途可互相切换，公式先于步骤且明确标出粘贴位置", async ({ page }) => {
  await page.goto("/tools/excel-formulas");
  const directory = page.getByRole("navigation", { name: "公式教程目录" });
  const search = page.getByRole("searchbox", { name: "搜索教程" });
  const categories = page.getByRole("group", { name: "教程分类" });
  await page.getByRole("button", { name: "查人员资料", exact: true }).click();
  await page.getByTestId("task-recommendations").getByRole("button").filter({ hasText: "按工号找到这个人的部门" }).click();
  await expect(page.getByTestId("lesson-selection-tip")).toContainText("从每人一行的名单中查出姓名或部门，用 VLOOKUP。");
  await expect(page.getByTestId("paste-target")).toHaveText("粘贴位置：练习表 C6");

  // 关联教程必须清除不兼容的任务、搜索和分类，不能正文切了而目录仍只显示旧任务。
  await search.fill("这个词不会命中任何教程");
  await categories.getByRole("button", { name: "文字与数字", exact: true }).click();
  await page.getByRole("button", { name: "同一个人有多笔金额？查看按人汇总", exact: true }).click();
  await expect(page).toHaveURL(/lesson=person-total/);
  await expect(page.getByTestId("lesson-selection-tip")).toContainText("把同一个人的多笔金额加在一起，用 SUMIFS。");
  await expect(page.getByTestId("paste-target")).toHaveText("粘贴位置：练习表 C3");
  await expect(search).toHaveValue("");
  await expect(directory.getByRole("button")).toHaveCount(50);
  await expect(directory).toContainText("同一个人有多笔，算他的总金额");
  expect(await page.getByTestId("formula-recipe").evaluate((recipe) => {
    const steps = document.querySelector('[data-testid="lesson-steps"]');
    return steps !== null && Boolean(recipe.compareDocumentPosition(steps) & Node.DOCUMENT_POSITION_FOLLOWING);
  })).toBe(true);

  await page.getByRole("button", { name: "只想查姓名或部门？查看查人员资料", exact: true }).click();
  await expect(page).toHaveURL(/lesson=employee-lookup/);
  await expect(page.getByTestId("paste-target")).toHaveText("粘贴位置：练习表 C6");
  await page.getByRole("button", { name: "数记录条数", exact: true }).click();
  await page.getByTestId("task-recommendations").getByRole("button").filter({ hasText: "数一数有多少条记录符合条件" }).click();
  await expect(page.getByTestId("lesson-selection-tip")).toContainText("这里数的是记录条数，同一个人有多条记录时会重复计数。");
  await expect(page.getByTestId("paste-target")).toHaveText("粘贴位置：练习表 C5");

  // 浏览器后退到另一用途时，退出旧任务过滤，避免当前教程从目录中消失。
  await page.goBack();
  await expect(page).toHaveURL(/lesson=employee-lookup/);
  await expect(page.getByTestId("paste-target")).toHaveText("粘贴位置：练习表 C6");
  await expect(directory.getByRole("button")).toHaveCount(50);
  await expect(page.getByRole("button", { name: "数记录条数", exact: true })).toHaveAttribute("aria-pressed", "false");
  await page.goForward();
  await expect(page.getByTestId("paste-target")).toHaveText("粘贴位置：练习表 C5");
});

test("直接标明适用范围，全部教程可选且新版教程始终提供旧版替代入口", async ({ page }) => {
  await page.goto("/tools");
  await expect(page.getByText("办公工具 · 50 篇完整教程", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "打开工具" }).click();
  const directory = page.getByRole("navigation", { name: "公式教程目录" });
  await expect(page.getByRole("combobox")).toHaveCount(0);
  await expect(page.getByText("按 Excel 版本找教程", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("searchbox", { name: "搜索教程" })).toHaveAttribute("placeholder", "按人员汇总、查找重复项、核对提交名单");
  await expect(directory.getByRole("button")).toHaveCount(50);

  // 不要求先选版本，候选教程直接说明兼容范围。
  await page.getByRole("button", { name: "查人员资料", exact: true }).click();
  await expect(directory.getByRole("button")).toHaveCount(4);
  await expect(page.getByTestId("task-recommendations").getByRole("button").filter({ hasText: "用新版公式按工号查部门" })).toContainText("Excel 2021 及以上，或 Microsoft 365");
  const samples = [
    ["person-total", "Excel 2016 及以上", false],
    ["join-roster", "Excel 2019 及以上", true],
    ["xlookup-department", "Excel 2021 及以上，或 Microsoft 365", true],
    ["filter-completed", "Excel 2021 及以上，或 Microsoft 365", true],
    ["unique-employees", "Excel 2021 及以上，或 Microsoft 365", true],
    ["sort-amounts", "Excel 2021 及以上，或 Microsoft 365", true],
  ] as const;
  for (const [id, range, hasAlternative] of samples) {
    await page.goto(`/tools/excel-formulas?lesson=${id}`);
    await expect(page.getByRole("combobox")).toHaveCount(0);
    await expect(directory.getByRole("button")).toHaveCount(50);
    await expect(page.getByTestId("lesson-content").locator(".formula-version")).toContainText(`适用范围：${range}`);
    const alternative = page.getByRole("link", { name: "查看旧版替代方法", exact: true });
    await expect(alternative).toHaveCount(hasAlternative ? 1 : 0);
    if (hasAlternative) {
      await alternative.click();
      await expect(page.getByRole("heading", { name: "换成你自己的表格", exact: true })).toBeInViewport();
    }
  }
});

test("长练习表保留真实行号，新版公式在独立空白区域一次展开", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/tools/excel-formulas?lesson=top-amount");
  const sheetTabs = page.getByRole("group", { name: "示例工作表" });
  await sheetTabs.getByRole("button", { name: "练习", exact: true }).click();
  const table = page.getByRole("table");
  await expect(table.getByRole("rowheader", { name: "47", exact: true })).toBeVisible();
  await expect(table.getByRole("rowheader", { name: "48", exact: true })).toBeVisible();
  await expect(table.getByRole("rowheader", { name: "2", exact: true })).toHaveCount(0);
  await expect(table.locator(".is-target")).toHaveCount(1);
  await expect(table.locator(".is-target")).toHaveText("在此输入公式");
  await expect(page.getByTestId("paste-target")).toHaveText("粘贴位置：练习表 C48");
  // 先检查真实容器内的横向位置，不能让测试框架自动滚动掩盖目标列在屏外的问题。
  await expect.poll(() => table.locator(".is-target").evaluate((cell) => {
    const frame = cell.closest(".formula-sheet-scroll")?.getBoundingClientRect();
    const target = cell.getBoundingClientRect();
    return Boolean(frame && target.left >= frame.left && target.right <= frame.right);
  })).toBe(true);
  await table.scrollIntoViewIfNeeded();
  await expect(table.locator(".is-target")).toBeInViewport();
  await expect(table.getByRole("rowheader", { name: "48", exact: true })).toBeInViewport();

  const spillExercises = [
    { id: "filter-completed", sheet: "筛选练习", fn: "FILTER(", first: "张三", expected: "张三、李四、王五、赵六（纵向 4 行）", rows: 4 },
    { id: "unique-employees", sheet: "去重练习", fn: "UNIQUE(", first: "U001", expected: "U001、U002、U003、U004（纵向 4 行）", rows: 4 },
    { id: "sort-amounts", sheet: "排序练习", fn: "SORT(", first: "300", expected: "300、200、150、120、80、50（纵向 6 行）", rows: 6 },
  ];
  for (const exercise of spillExercises) {
    await page.goto(`/tools/excel-formulas?lesson=${exercise.id}`);
    await sheetTabs.getByRole("button", { name: exercise.sheet, exact: true }).click();
    await expect(sheetTabs.getByRole("button")).toHaveCount(2);
    await expect(table.locator("tbody tr")).toHaveCount(exercise.rows);
    await expect(table.locator(".is-target")).toHaveCount(1);
    await expect(table.locator(".is-target")).toHaveText("在此输入公式");
    await expect(table.locator("tbody tr").first().getByRole("rowheader")).toHaveText("2");
    await expect(table.locator("tbody tr").first().getByRole("cell").nth(2)).toHaveText(exercise.first);
    await expect(page.getByTestId("paste-target")).toHaveText(`粘贴位置：${exercise.sheet}表 A2`);
    await expect(page.getByTestId("lesson-formula")).toContainText(exercise.fn);
    await expect(page.getByTestId("expected-result")).toHaveText(exercise.expected);
    await expect(page.getByTestId("lesson-content").locator(".formula-version")).toContainText("2021");
    expect(await page.getByTestId("lesson-steps").getByRole("listitem").count()).toBeGreaterThanOrEqual(6);
    await expect(page.getByTestId("lesson-steps")).toContainText("A2");
    await expect(page.getByTestId("lesson-content")).toContainText("一次");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  }
});
