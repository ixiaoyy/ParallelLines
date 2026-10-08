from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import date

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.openai_chat import (
    extract_chat_content,
    extract_json_object,
    request_openai_chat,
)

DAILY_READING_TAGS = ("读书", "原创")
DAILY_READING_SYSTEM_PROMPT = """
你为中文小论坛里的普通用户写每日读书感悟。这个账号是戴眼镜、喜欢二次元和游戏的年轻女性，
但阅读只是她生活的一部分，不要刻意堆游戏梗、宅文化符号或文艺人设。

一次只生成两篇彼此明显不同的原创帖子，并严格遵守：
1. 每篇可以提到一本真实书籍，但只写宽泛、可靠的阅读感受；不编造情节、作者经历或出版信息。
2. 不直接摘抄书中原句，不伪造引语，不复述大段受版权保护的文字。
3. 用自然的一人称口吻，像普通用户读了几页后随手写下的想法，不像书评、营销稿或 AI 总结。
4. 每篇正文 220 至 520 个中文字符，分成 3 至 5 个短段落；标题 8 至 40 个中文字符。
5. 两篇不能写同一本书、同一种阅读方法或同一个结论，也不要使用近期标题的改写。
6. 不写新闻、时效事实、网址、商品推荐、医疗建议、政治观点或身份声明。
7. 只返回一个 JSON 对象，结构必须是：
   {"posts":[{"title":"...","body":"..."},{"title":"...","body":"..."}]}
""".strip()


@dataclass(frozen=True)
class DailyReadingDraft:
    """Store one validated daily reading topic draft without database identity."""

    title: str
    raw_md: str
    tags: tuple[str, ...] = DAILY_READING_TAGS

    def to_dict(self) -> dict[str, object]:
        """Return this draft as JSON-safe plan storage data without side effects."""

        return {"title": self.title, "raw_md": self.raw_md, "tags": list(self.tags)}


@dataclass(frozen=True)
class DailyReadingProviderResult:
    """Describe two generated drafts and the provider provenance used for them."""

    drafts: tuple[DailyReadingDraft, DailyReadingDraft]
    model_name: str
    provider_mode: str


class DailyReadingProvider:
    """Define the asynchronous content-provider contract for one local reading day."""

    async def generate(
        self,
        planned_date: date,
        recent_titles: list[str],
    ) -> DailyReadingProviderResult:
        """Generate exactly two validated drafts for a date without database writes."""

        raise NotImplementedError


class OpenAICompatibleDailyReadingProvider(DailyReadingProvider):
    """Generate daily reading drafts through the shared OpenAI-compatible boundary."""

    def __init__(self, settings: Settings, api_key: str) -> None:
        """Store runtime model settings and one server-side credential without I/O."""

        self.settings = settings
        self.api_key = api_key

    async def generate(
        self,
        planned_date: date,
        recent_titles: list[str],
    ) -> DailyReadingProviderResult:
        """Request two drafts for a date and return validated model output.

        Key parameters are the Shanghai calendar date and recent published titles.
        The return value contains exactly two drafts. Side effect: performs one
        outbound model request without logging its credential or response body.
        """

        messages = build_daily_reading_messages(planned_date, recent_titles)
        payload = await asyncio.to_thread(
            request_openai_chat,
            base_url=self.settings.daily_reading_ai_base_url,
            api_key=self.api_key,
            model=self.settings.daily_reading_ai_model,
            messages=messages,
            temperature=self.settings.daily_reading_ai_temperature,
            max_tokens=self.settings.daily_reading_ai_max_tokens,
            timeout_seconds=self.settings.daily_reading_ai_timeout_seconds,
            error_prefix="daily_reading_provider",
            service_label="每日读书内容模型",
        )
        result = parse_daily_reading_provider_result(
            payload,
            fallback_model=self.settings.daily_reading_ai_model,
        )
        ensure_daily_reading_titles_fresh(result.drafts, recent_titles)
        return result


class LocalDailyReadingProvider(DailyReadingProvider):
    """Build deterministic original fallback drafts without external services."""

    async def generate(
        self,
        planned_date: date,
        recent_titles: list[str],
    ) -> DailyReadingProviderResult:
        """Return two date-stable local drafts without network or database writes."""

        del recent_titles
        return DailyReadingProviderResult(
            drafts=build_local_daily_reading_drafts(planned_date),
            model_name="local-daily-reading-v1",
            provider_mode="local_fallback",
        )


def configured_daily_reading_provider(
    settings: Settings,
) -> tuple[DailyReadingProvider, bool]:
    """Return the configured provider and whether model fallback handling is needed.

    Key parameter is runtime settings. The return value pairs a provider with an
    AI-enabled flag. Side effect: none; credentials remain server-side.
    """

    api_key = (
        settings.daily_reading_ai_api_key
        or settings.daily_report_ai_api_key
        or settings.opencode_api_key
    ).strip()
    if settings.daily_reading_ai_provider != "local" and api_key:
        return OpenAICompatibleDailyReadingProvider(settings, api_key), True
    return LocalDailyReadingProvider(), False


async def generate_daily_reading_with_fallback(
    settings: Settings,
    planned_date: date,
    recent_titles: list[str],
    *,
    force_local: bool = False,
) -> DailyReadingProviderResult:
    """Generate two daily drafts and fall back to deterministic local content.

    Key parameters select settings, date, recent-title avoidance context, and an
    optional local-only mode. Return value always contains two validated drafts.
    Side effect may be one outbound model request when configured.
    """

    if force_local:
        return await LocalDailyReadingProvider().generate(planned_date, recent_titles)
    provider, ai_enabled = configured_daily_reading_provider(settings)
    try:
        return await provider.generate(planned_date, recent_titles)
    except AppError:
        if not ai_enabled:
            raise
        return await LocalDailyReadingProvider().generate(planned_date, recent_titles)


def build_daily_reading_messages(
    planned_date: date,
    recent_titles: list[str],
) -> list[dict[str, str]]:
    """Build bounded provider messages for one date without including private data."""

    context = {
        "planned_date": planned_date.isoformat(),
        "recent_titles_to_avoid": recent_titles[:60],
        "required_count": 2,
    }
    return [
        {"role": "system", "content": DAILY_READING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "请按约定生成今天的两篇读书感悟。上下文：\n"
            + json.dumps(context, ensure_ascii=False),
        },
    ]


def parse_daily_reading_provider_result(
    response: dict[str, object],
    *,
    fallback_model: str,
) -> DailyReadingProviderResult:
    """Parse and validate two drafts from an OpenAI-compatible response payload."""

    content = extract_chat_content(
        response,
        error_prefix="daily_reading_provider",
        service_label="每日读书内容模型",
    )
    payload = extract_json_object(
        content,
        error_prefix="daily_reading_provider",
        service_label="每日读书内容模型",
    )
    drafts = parse_daily_reading_drafts(payload)
    return DailyReadingProviderResult(
        drafts=drafts,
        model_name=str(response.get("model") or fallback_model)[:120],
        provider_mode="ai",
    )


def parse_daily_reading_drafts(
    payload: dict[str, object],
) -> tuple[DailyReadingDraft, DailyReadingDraft]:
    """Validate a stored or provider-produced object as exactly two reading drafts."""

    posts = payload.get("posts")
    if not isinstance(posts, list) or len(posts) != 2:
        raise AppError(
            "daily_reading_provider_invalid_response",
            "每日读书内容模型没有返回两篇帖子",
            status_code=503,
        )
    drafts: list[DailyReadingDraft] = []
    normalized_titles: set[str] = set()
    for post in posts:
        if not isinstance(post, dict):
            raise _invalid_daily_reading_response("帖子结构无效")
        title = post.get("title")
        raw_md = post.get("body") if "body" in post else post.get("raw_md")
        if not isinstance(title, str) or not isinstance(raw_md, str):
            raise _invalid_daily_reading_response("帖子缺少标题或正文")
        title = " ".join(title.split()).strip("# ")
        raw_md = raw_md.strip()
        if not 4 <= len(title) <= 80:
            raise _invalid_daily_reading_response("帖子标题长度无效")
        if not 180 <= len(raw_md) <= 800:
            raise _invalid_daily_reading_response("帖子正文长度无效")
        normalized_title = "".join(title.lower().split())
        if normalized_title in normalized_titles:
            raise _invalid_daily_reading_response("两篇帖子标题重复")
        normalized_titles.add(normalized_title)
        drafts.append(DailyReadingDraft(title=title, raw_md=raw_md))
    return drafts[0], drafts[1]


def ensure_daily_reading_titles_fresh(
    drafts: tuple[DailyReadingDraft, DailyReadingDraft],
    recent_titles: list[str],
) -> None:
    """Reject provider titles that exactly repeat recent published titles.

    Key parameters are the two new drafts and bounded recent-title context.
    Return value is none. Side effect: raises a safe provider error on a repeat.
    """

    recent = {"".join(title.lower().split()) for title in recent_titles if title.strip()}
    repeated = [draft.title for draft in drafts if "".join(draft.title.lower().split()) in recent]
    if repeated:
        raise _invalid_daily_reading_response("帖子标题与近期内容重复")


def _invalid_daily_reading_response(detail: str) -> AppError:
    """Build one safe provider-contract error without exposing generated content."""

    return AppError(
        "daily_reading_provider_invalid_response",
        f"每日读书内容模型返回无效内容：{detail}",
        status_code=503,
    )


@dataclass(frozen=True)
class LocalBookSeed:
    """Hold one broadly verifiable book theme for deterministic local drafts."""

    book: str
    focus: str
    observation: str
    question: str


@dataclass(frozen=True)
class LocalReadingLens:
    """Hold one natural reading situation that can frame any curated book theme."""

    title: str
    scene: str
    practice: str


@dataclass(frozen=True)
class LocalReadingClosing:
    """Hold one title frame and closing thought for local combination diversity."""

    title_frame: str
    ending: str


LOCAL_BOOK_SEEDS: tuple[LocalBookSeed, ...] = (
    LocalBookSeed(
        "活着",
        "一个普通人在接连失去之后仍然继续生活",
        "它没有把坚持写成响亮的胜利，更像是把日子一天天接下去。",
        "如果生活没有立刻给出回报，人靠什么把今天过完？",
    ),
    LocalBookSeed(
        "小王子",
        "关系需要时间，也伴随着照料和责任",
        "真正重要的联系不是突然发生的，而是在一次次靠近里慢慢形成。",
        "我愿意把时间留给什么，也就说明我在意什么吗？",
    ),
    LocalBookSeed(
        "老人与海",
        "一个人如何面对结果之外的坚持",
        "故事让我看到，努力并不总能换来完整的收获，但过程仍会改变一个人。",
        "如果结局不理想，之前付出的力气还算不算数？",
    ),
    LocalBookSeed(
        "局外人",
        "个人感受和社会期待之间的不合拍",
        "读着会不舒服，因为周围人常常不仅判断行为，也要求一个人表现出正确的情绪。",
        "我们是在理解别人，还是在检查别人有没有按规则表达？",
    ),
    LocalBookSeed(
        "月亮与六便士",
        "追逐欲望时伴随的代价和伤害",
        "它让我很难只把选择浪漫化，因为一个人的自由可能落在另一些人的生活上。",
        "谈理想的时候，是不是也该把它带来的成本算进去？",
    ),
    LocalBookSeed(
        "百年孤独",
        "家族记忆里反复出现的名字、性格和选择",
        "那些循环读起来像命运，也像人没有真正看清上一代留下的问题。",
        "如果一种模式总在重复，察觉它是不是改变的第一步？",
    ),
    LocalBookSeed(
        "瓦尔登湖",
        "主动辨认需要和欲望之间的距离",
        "我不太想照搬书里的生活方式，但会被它追问：哪些忙碌其实可以少一点。",
        "把生活简化之后，我真正舍不得放下的会是什么？",
    ),
    LocalBookSeed(
        "沉思录",
        "把注意力放回自己的判断和行动",
        "很多提醒看起来朴素，难的是情绪上来时还能不能记得自己的边界。",
        "今天有哪些事不由我决定，但回应方式仍然属于我？",
    ),
    LocalBookSeed(
        "悉达多",
        "听来的知识和亲自经历之间的距离",
        "别人总结得再清楚，也不能替一个人完成自己的体验和理解。",
        "我是不是有时太急着借用别人的答案？",
    ),
    LocalBookSeed(
        "杀死一只知更鸟",
        "偏见如何藏在习以为常的目光里",
        "它提醒我，站到另一个人的位置并不等于马上赞同，而是先承认自己的视角有限。",
        "下判断之前，我有没有漏掉对方正在承受的处境？",
    ),
    LocalBookSeed(
        "追风筝的人",
        "愧疚之后漫长而不轻松的修补",
        "弥补并不能让过去消失，但逃避只会让旧事一直停在原处。",
        "真正的补偿，是减轻自己的难受，还是承担对别人造成的影响？",
    ),
    LocalBookSeed(
        "额尔古纳河右岸",
        "个人生活、族群记忆和自然环境交织在一起",
        "时间在书里不是简单往前走，很多离开都同时改变了人与土地的关系。",
        "记录一段生活时，怎样才不把它缩成几句方便理解的话？",
    ),
    LocalBookSeed(
        "平凡的世界",
        "普通人在劳动、选择和限制中维护自己的尊严",
        "它让我重新注意那些没有戏剧性，却需要长期用力的日常。",
        "一个人的价值，是否一定要靠显眼的结果来证明？",
    ),
    LocalBookSeed(
        "长安的荔枝",
        "看似简单的目标如何在层层传递中变成具体压力",
        "读的时候很容易想到工作里那些一句话布置下来、最后由许多人填补细节的任务。",
        "面对不合理的目标，除了硬扛之外还能怎样保留判断？",
    ),
    LocalBookSeed(
        "也许你该找个人聊聊",
        "帮助别人和理解自己并不是两件分开的事",
        "人很擅长讲一个能自洽的故事，却未必马上看见故事里被跳过的部分。",
        "我反复解释的事情里，有没有一个自己一直避开的角度？",
    ),
    LocalBookSeed(
        "山茶文具店",
        "替人写信时对语气、关系和未说出口之事的体会",
        "一封信不只传递内容，也保存了写信的人愿意如何靠近另一个人。",
        "有些话换一种更慢的方式写出来，会不会更接近本意？",
    ),
    LocalBookSeed(
        "思考，快与慢",
        "直觉判断和费力思考会在不同场景里接管决定",
        "知道偏差的名字并不会自动免疫，但至少能提醒我在重要选择前多停一下。",
        "哪些决定看起来很顺，其实只是因为答案最先跳了出来？",
    ),
    LocalBookSeed(
        "被讨厌的勇气",
        "人际边界和对自己选择的负责",
        "我不一定接受书里的每个推论，但它确实逼我区分关心别人和替别人生活。",
        "尊重一段关系，是否也包括允许对方拥有不同的判断？",
    ),
    LocalBookSeed(
        "人类简史",
        "共同叙事如何帮助陌生人形成大规模协作",
        "很多习以为常的制度并不是天然存在，而是因为足够多人愿意共同相信和维护。",
        "看见规则是被建构的，会让我更轻率，还是更愿意承担维护它的责任？",
    ),
    LocalBookSeed(
        "献给阿尔吉侬的花束",
        "能力变化之中，一个人如何被看见和对待",
        "最难受的部分并不只关于聪明，而是尊严常被别人用能力高低来衡量。",
        "当一个人无法满足期待时，我们还愿不愿意认真听他说话？",
    ),
)

LOCAL_READING_LENSES: tuple[LocalReadingLens, ...] = (
    LocalReadingLens(
        "先别急着把它变成结论",
        "我本来想顺手总结成一句道理，写到一半又删掉了。",
        "先把问题留到明天，再看自己的第一反应会不会变化",
    ),
    LocalReadingLens(
        "隔了一晚才想明白一点",
        "昨晚读完没有记笔记，今天做别的事时反而又想起那一段。",
        "不追着复述内容，只写下它后来在哪个时刻重新出现",
    ),
    LocalReadingLens(
        "没划线的地方反而留下来了",
        "当时觉得平常的一段，合上书后却比那些漂亮句子更清楚。",
        "少收集一句摘抄，多补一句它为什么和自己有关",
    ),
    LocalReadingLens(
        "读到一半停下来也没关系",
        "今天注意力不太够，读了几页就放下了，没有逼自己凑进度。",
        "下一次从真正想接着看的地方开始，不把页数当成任务",
    ),
    LocalReadingLens(
        "同一段在不同心情里会变",
        "以前经过这里时没什么感觉，这次却因为最近的状态多停了一会儿。",
        "在旧笔记旁边加上今天的理解，允许两个答案同时存在",
    ),
    LocalReadingLens(
        "我只想记住一个小动作",
        "比起把整本书讲清楚，我更想知道它能不能轻轻改变一个日常选择。",
        "挑一个不费力的小动作试一天，不要求它立刻变成习惯",
    ),
    LocalReadingLens(
        "不认同的部分也值得留下",
        "这次没有因为几处不赞同就把整本书推开，反而把分歧单独记了下来。",
        "写清自己为什么不同意，也给以后改变看法留一点空间",
    ),
    LocalReadingLens(
        "从人物身上绕回自己的日常",
        "读别人的处境时很容易看得清楚，轮到自己却常用一句忙或没办法带过。",
        "找一个相似但更小的生活场景，看看自己当时是怎么选择的",
    ),
    LocalReadingLens(
        "把摘抄换成了自己的话",
        "以前的笔记里有很多完整句子，过一阵却想不起自己为什么抄它。",
        "合上书后再写，哪怕只剩很朴素的一两句话",
    ),
    LocalReadingLens(
        "没读完先留一个问题",
        "我发现带着问题继续读，比急着猜作者最后会给什么答案更有意思。",
        "把现在最困惑的一点写在页边，读完后再回来回答",
    ),
    LocalReadingLens(
        "重读时看见了以前略过的地方",
        "情节大概还记得，真正陌生的反而是当时那个读书的自己。",
        "保留旧标记，不覆盖它，只在旁边补上这次看到的差异",
    ),
    LocalReadingLens(
        "这次不追求把书讲完整",
        "一想到要写完整书评就不想动笔，改成只记一个片段后轻松了很多。",
        "只回答这段为什么让我停下，不替整本书下结论",
    ),
)

LOCAL_READING_CLOSINGS: tuple[LocalReadingClosing, ...] = (
    LocalReadingClosing("读《{book}》：{angle}", "能留下一个真实问题，就已经不是白读。"),
    LocalReadingClosing(
        "《{book}》随手记：{angle}",
        "书没有替我做决定，但把那个决定照得更清楚了一点。",
    ),
    LocalReadingClosing(
        "今晚读到《{book}》：{angle}",
        "这种很小的变化，比记住一串漂亮句子更让我安心。",
    ),
    LocalReadingClosing(
        "关于《{book}》：{angle}",
        "暂时没有标准答案也没关系，下一次读到这里也许还会变。",
    ),
    LocalReadingClosing(
        "翻完几页《{book}》：{angle}",
        "阅读真正进入生活，大概就是从这种不显眼的停顿开始。",
    ),
    LocalReadingClosing(
        "这次读《{book}》：{angle}",
        "先做到这一点就够了，不必把每次阅读都变成一次自我改造。",
    ),
    LocalReadingClosing(
        "《{book}》读后小记：{angle}",
        "等过几天再翻这条笔记，我也想看看自己还同不同意。",
    ),
    LocalReadingClosing(
        "读书碎片｜《{book}》：{angle}",
        "一本书能让熟悉的日常稍微陌生一点，我就觉得这几页值得。",
    ),
)


def build_local_daily_reading_drafts(
    planned_date: date,
) -> tuple[DailyReadingDraft, DailyReadingDraft]:
    """Build two distinct date-stable fallback drafts from curated combinations.

    Key parameter is the Shanghai calendar date. The return value contains two
    different books and cycles only after 960 days. Side effect: none.
    """

    combination_count = (
        len(LOCAL_BOOK_SEEDS) * len(LOCAL_READING_LENSES) * len(LOCAL_READING_CLOSINGS)
    )
    drafts = []
    for slot in range(2):
        logical_index = (planned_date.toordinal() * 2 + slot) % combination_count
        combination_index = logical_index * 421 % combination_count
        drafts.append(_build_local_daily_reading_draft(combination_index))
    return drafts[0], drafts[1]


def _build_local_daily_reading_draft(combination_index: int) -> DailyReadingDraft:
    """Render one curated book/lens/closing combination as an original draft."""

    book_index = combination_index % len(LOCAL_BOOK_SEEDS)
    lens_index = (combination_index // len(LOCAL_BOOK_SEEDS)) % len(LOCAL_READING_LENSES)
    closing_index = (
        combination_index // (len(LOCAL_BOOK_SEEDS) * len(LOCAL_READING_LENSES))
    ) % len(LOCAL_READING_CLOSINGS)
    book = LOCAL_BOOK_SEEDS[book_index]
    lens = LOCAL_READING_LENSES[lens_index]
    closing = LOCAL_READING_CLOSINGS[closing_index]
    title = closing.title_frame.format(book=book.book, angle=lens.title)
    raw_md = (
        f"这两天在读《{book.book}》。这次让我停下来的不是某句适合摘抄的话，"
        f"而是{book.focus}。{book.observation}\n\n"
        f"{lens.scene}我发现自己以前总想把读后感写成一个完整结论，"
        f"但这次更愿意先保留那个不太确定的地方：{book.question}\n\n"
        f"所以今天只给自己留一个小动作：{lens.practice}。{closing.ending}"
    )
    return DailyReadingDraft(title=title, raw_md=raw_md)
