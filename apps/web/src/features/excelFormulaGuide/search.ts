import type { FormulaLesson } from "./model";

/** 统一全角字符、大小写及括号问句标点，保留否定词、运算符和关键词间的空格。 */
function normalizeSearchText(value: string): string {
  return value.normalize("NFKC").toLowerCase().replace(/[()[\]{}"'「」『』\u201c\u201d,、;:。?!]/gu, " ").replace(/\s+/g, " ").trim();
}

/** 去除有限的问句修饰，返回仍保留计算对象和条件语义的检索词。 */
function simplifyQuestion(value: string): string {
  let result = value;
  // 只处理句首的礼貌用语和提问方式，次数有界，不删除句中的不、任一、同时等条件。
  for (let index = 0; index < 4; index += 1) {
    const next = result.replace(/^(?:请问|请|麻烦你|麻烦|帮我|我想要|我想|我要|想要|如何|怎样|怎么|计算|算一下|算一算|算)\s*/u, "");
    if (next === result) break;
    result = next;
  }
  return result.replace(/(?:怎么用|如何使用|用什么公式|用哪个公式|呢|吗)$/u, "").trim();
}

/** 只识别完整匹配的常见问句；附加动作、否定或筛选条件交还字面检索。 */
function findQuestionIntent(query: string): string | undefined {
  // 生成不重复名单与标记重复记录分别识别，不依赖相同子串推测用途。
  if (/^(?:(?:找出|查找|生成|提取|列出)(?:一下)?)?(?:不重复(?:的)?(?:人|人员|姓名|工号|名单|记录|工号名单|人员名单|姓名名单)|(?:人|人员|姓名|工号|名单)?去重|唯一值|不重复)$/u.test(query)) return "unique-employees";
  if (/^(?:(?:找出|查找|检查|标记)(?:一下)?)?(?:重复(?:出现)?(?:的)?(?:人|人员|姓名|工号|名单|记录)|(?:人|人员|姓名|工号|名单)(?:是否)?重复|查重|重复)$/u.test(query)) return "duplicate-id";

  // 判断全部或任一条件的模板不接受附加金额、计数或否定要求。
  if (/^(?:(?:两个|多个)条件(?:都|同时)满足|(?:全部|所有)(?:条件)?(?:都)?满足|同时满足(?:(?:两个|多个|全部|所有)?条件)?)$/u.test(query)) return "and-conditions";
  if (/^(?:(?:只要|只需)(?:满足)?(?:其中|任意|至少)?一个条件(?:满足)?|(?:任一|任意一个|其中一个|至少一个)条件(?:满足)?|满足(?:任一|任意一个|其中一个|至少一个)条件|满足(?:其中|任意|至少)?一个条件(?:就行|即可))$/u.test(query)) return "or-conditions";

  // 仅接受提取尾号的完整表达，隐藏或替换尾号不属于 RIGHT 这篇教程。
  if (/^(?:把|将)?(?:手机号|手机号码|电话号码|电话)(?:的)?后(?:四|4)位(?:取出来|提取出来|取出|提取)?$/u.test(query)
    || /^(?:提取|取出)(?:手机号|手机号码|电话号码|电话)(?:的)?后(?:四|4)位$/u.test(query)) return "right-phone";
  if (/^(?:(?:计算|统计|求|算)(?:一下)?)?(?:一个人|同一个人|每个人|按人|按姓名|按工号|个人)(?:的)?(?:总金额|总额|合计(?:金额)?|汇总(?:金额)?|金额合计|金额汇总)(?:怎么(?:算|计算))?$/u.test(query)) return "person-total";
  return undefined;
}

/**
 * 判断一篇教程是否匹配用户输入；空输入显示全部，多空格关键词仍须全部命中。
 * 只在单个自然语言问句中采用明确的场景识别，不把未知问句兜底到任意教程。
 */
export function matchesLessonSearch(lesson: FormulaLesson, query: string): boolean {
  const normalized = normalizeSearchText(query);
  if (!normalized) return true;
  const words = normalized.split(" ");
  const simplified = simplifyQuestion(normalized);
  const text = normalizeSearchText([lesson.title, lesson.summary, ...lesson.functions, ...lesson.keywords].join(" "));

  // 显式否定和逻辑条件优先于旧关键词别名，避免名单去重误命中查重教程。
  if (lesson.id === "duplicate-id" && /不重复|去重|唯一值/u.test(normalized)) return false;
  const allConditions = /同时满足|全部(?:条件)?(?:都)?满足|所有(?:条件)?(?:都)?满足/u.test(normalized);
  const anyCondition = /任(?:意)?一(?:个)?|其中一个|至少一个/u.test(normalized);
  if (lesson.id === "or-conditions" && allConditions && !anyCondition) return false;
  if (lesson.id === "and-conditions" && anyCondition && !allConditions) return false;

  // 带空格的输入保留原有全部匹配规则；单个问句才允许按明确意图定位。
  if (words.length === 1) {
    const intent = findQuestionIntent(simplified);
    if (intent) return lesson.id === intent;
  }
  if (words.every((word) => text.includes(word))) return true;
  return simplified !== "" && simplified !== normalized
    && simplified.split(" ").every((word) => text.includes(word));
}
