from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import configure_logging
from app.core.personas import PersonaKind, seeded_persona_kind
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.forum import Board
from app.models.moderation import Reviewable
from app.models.user import User
from app.services.forum import ForumService, normalize_tag_name
from app.services.moderation import ModerationService

BATCH_KEY = "persona-articles-v1"
SOURCE = "persona_content"
SOURCE_SUMMARY = "新用户发帖，发布前需要审核通过。"


@dataclass(frozen=True)
class PersonaSpec:
    username: str
    email: str
    bio: str
    avatar_url: str | None = None


@dataclass(frozen=True)
class ArticleSpec:
    board_slug: str
    author: str
    title: str
    body: str
    tags: tuple[str, ...]


PERSONAS: tuple[PersonaSpec, ...] = (
    PersonaSpec(
        "不吃香菜的猫",
        "no-coriander-cat@pingxingxian.space",
        "不太会写长篇，想到什么说什么。",
    ),
    PersonaSpec(
        "一杯冰美式续命",
        "iced-americano@pingxingxian.space",
        "靠咖啡和一点点好心情撑住工作日。",
    ),
    PersonaSpec(
        "外卖备注写错了",
        "waimai-note@pingxingxian.space",
        "经常在小事上翻车，也经常被小事治好。",
    ),
    PersonaSpec("冰箱里还有半瓶可乐", "half-cola@pingxingxian.space", "普通生活记录员。"),
    PersonaSpec("刚下班别催", "offwork-no-push@pingxingxian.space", "下班后慢半拍回复。"),
    PersonaSpec("雾里看山", "fog-mountain@pingxingxian.space", "喜欢慢慢读、慢慢走。"),
    PersonaSpec("远山便利店", "yuanshan-shop@pingxingxian.space", "收藏一些顺手的小工具。"),
    PersonaSpec("老槐", "old-huai-tree@pingxingxian.space", "偶尔认真，偶尔摆烂。"),
    PersonaSpec("oldhuai", "oldhuai@pingxingxian.space", "路过看看，也会留两句。"),
    PersonaSpec("huai_07", "huai-07@pingxingxian.space", "对产品细节有点挑。"),
    PersonaSpec("Aki_慢慢来", "aki-slow@pingxingxian.space", "慢慢做也算做。"),
    PersonaSpec(
        "momo-离线",
        "momo-offline@pingxingxian.space",
        "替没说出口的人把故事写完。内容均为虚构，每天一集。",
        "/avatars/momo-offline.png",
    ),
    PersonaSpec("kk不在线", "kk-offline@pingxingxian.space", "收藏夹总是爆满。"),
    PersonaSpec(
        "Nate_路过",
        "nate-passby@pingxingxian.space",
        "话不多，常常把一句话在输入框里改很多遍。",
        "/avatars/nate-passing-heart.png",
    ),
    PersonaSpec("小K_再看看", "xiaok-look@pingxingxian.space", "先看看，再决定。"),
    PersonaSpec("rain_404", "rain404@pingxingxian.space", "不太会坚持，但还在试。"),
    PersonaSpec("zzZ_醒了", "zzz-awake@pingxingxian.space", "每天都在和闹钟协商。"),
    PersonaSpec("beta路人", "beta-passer@pingxingxian.space", "偶尔捡到一些省钱小提醒。"),
    PersonaSpec("loop_一下", "loop-once@pingxingxian.space", "喜欢把问题绕回来再看一遍。"),
    PersonaSpec(
        "穿猫的靴子",
        "cat-boots@pingxingxian.space",
        "写点看到的变化和小趋势。",
        "/avatars/cat-boots-bronze.png",
    ),
    PersonaSpec(
        "小漫家",
        "xiaomanjia@pingxingxian.space",
        "把心动写成慢慢更新的小故事。虚构连载，每天一集。",
        "/avatars/xiaomanjia.png",
    ),
    PersonaSpec(
        "小瓜同学",
        "xiaogua@pingxingxian.space",
        "每天逛一圈热搜，只捡有意思又能聊的。",
        "/avatars/xiaogua.png",
    ),
    PersonaSpec(
        "页边有光",
        "page-margin-light@pingxingxian.space",
        "动画游戏都玩一点，偶尔记下读完几页后的想法。",
        "/avatars/page-margin-light.png",
    ),
    PersonaSpec("小小鸡仔", "xiaoxiao-jizai@pingxingxian.space", "小小鸡仔，偶尔啄两句。"),
)


def required_persona_kind(persona: PersonaSpec) -> PersonaKind:
    """Return one seed's approved kind or fail before any account write.

    The parameter is the configured persona. The return value is its exact
    username/email classification; this helper has no persistence side effects.
    """

    kind = seeded_persona_kind(persona.username, persona.email)
    if kind is None:
        raise RuntimeError(f"Missing approved persona classification: {persona.username}")
    return kind

LEGACY_PERSONA_RENAMES: tuple[tuple[str, str], ...] = (
    ("今天也想早睡", "不吃香菜的猫"),
    ("路过买杯奶茶", "一杯冰美式续命"),
    ("小鱼干没了", "外卖备注写错了"),
    ("键盘有点响", "冰箱里还有半瓶可乐"),
    ("周三不想开会", "刚下班别催"),
    ("隔壁老番茄", "雾里看山"),
    ("夜里两点半", "远山便利店"),
    ("多喝热水先别", "老槐"),
    ("有点想下班", "oldhuai"),
    ("山竹不剥皮", "huai_07"),
    ("工位种蘑菇", "Aki_慢慢来"),
    ("不想起标题", "momo-离线"),
    ("咖啡续命中", "kk不在线"),
    ("晚点再说吧", "Nate_路过"),
    ("半糖少冰啊", "小K_再看看"),
    ("猫在键盘上", "rain_404"),
    ("风吹过地铁口", "zzZ_醒了"),
    ("纸巾还剩一张", "beta路人"),
    ("蓝莓酸奶盖", "loop_一下"),
    ("明天再整理", "穿猫的靴子"),
)

ARTICLES: tuple[ArticleSpec, ...] = (
    ArticleSpec(
        "lounge",
        "不吃香菜的猫",
        "周末把冰箱清了一下，心里也轻了点",
        "周末本来只想拿瓶水，结果发现冰箱里塞了好多快忘掉的东西。半包青菜、两盒没吃完的酱，还有一瓶不知道什么时候开的饮料。\n\n我花了半小时全拿出来看了一遍，该扔的扔掉，该今天吃的放到前面。冰箱空下来以后，人也跟着松了一点。可能生活秩序就是从这种小角落开始回来的。",
        ("日常", "收拾"),
    ),
    ArticleSpec(
        "benefits",
        "一杯冰美式续命",
        "便利店第二杯半价其实也要冷静一下",
        "今天买咖啡又遇到第二杯半价。以前我会觉得不买亏了，最后多拿一杯，下午喝不完还心慌。\n\n现在我会先问自己：这杯是真的想喝，还是只是被优惠推着走？如果旁边没有同事刚好要，我就只买一杯。羊毛能薅，但别把自己薅累了。",
        ("羊毛", "咖啡"),
    ),
    ArticleSpec(
        "qna",
        "外卖备注写错了",
        "外卖备注老是出错，是不是我写太复杂了",
        "我点外卖经常备注一长串，比如少辣、不要葱、多放醋、米饭少一点。结果店里不是漏看，就是只做到其中一条。\n\n最近有点怀疑是我写得太复杂了。大家一般怎么写备注？是只写最重要的一条，还是分行写会更清楚？",
        ("求助", "外卖"),
    ),
    ArticleSpec(
        "lounge",
        "冰箱里还有半瓶可乐",
        "半瓶可乐放冰箱两天，快乐也只剩半瓶",
        "前天没喝完的可乐放在冰箱里，今天想起来拿出来喝，气已经跑得差不多了。\n\n这个事情很小，但我突然觉得很多东西都是这样，当下没享受完，放太久就不是原来的味道了。以后想喝就早点喝，想说的话也早点说。",
        ("生活", "随手记"),
    ),
    ArticleSpec(
        "experience",
        "刚下班别催",
        "下班后不马上回消息，真的舒服很多",
        "以前我一下班也会盯着手机，工作群一响就回。后来发现这样很难真正停下来，明明人到家了，脑子还在办公室。\n\n这两周我给自己定了个小规则：不是急事就晚饭后再看。刚开始会有点不安，现在好多了。下班后的半小时终于像自己的时间。",
        ("经验", "下班"),
    ),
    ArticleSpec(
        "reading",
        "雾里看山",
        "读书慢一点之后，反而记住得更多",
        "我以前读书总想快点看完，好像读完一本才算有收获。结果合上书以后，能记住的其实不多。\n\n最近改成每天只看十几页，看到有感觉的地方就停一下，写两句自己的话。进度慢了，但内容反而留下来了。可能读书不是赶路，慢一点也没关系。",
        ("读书", "方法"),
    ),
    ArticleSpec(
        "resources",
        "远山便利店",
        "分享几个我一直留着的小网页",
        "收藏夹里很多东西最后都不用了，但有几个小网页我一直没删：临时记事、图片压缩、文字去空行、在线计时器。\n\n它们共同点是不用注册，打开就能用。功能不花哨，但真到需要的时候很省事。大家如果也有这种朴素但好用的小工具，可以互相补一下。",
        ("工具", "分享"),
    ),
    ArticleSpec(
        "health",
        "老槐",
        "肩颈不舒服后，我把屏幕垫高了",
        "最近下午总觉得脖子紧，一开始以为是枕头问题。后来同事提醒我看屏幕的时候一直低着头。\n\n我把几本旧书垫到显示器下面，刚好让视线平一点。不是立刻好了，但下午没那么酸。上班族有些毛病，真的藏在很小的姿势里。",
        ("健康", "办公"),
    ),
    ArticleSpec(
        "news",
        "oldhuai",
        "最近大家又开始聊小屏手机了",
        "这几天看到好几个人在怀念小屏手机。以前都说屏幕越大越好，现在又有人想要轻一点、单手能握住的手机。\n\n我也有点理解。大屏看视频舒服，但通勤拿久了是真的累。手机如果只是工具，轻一点可能比大一点更重要。",
        ("趋势", "手机"),
    ),
    ArticleSpec(
        "feedback",
        "huai_07",
        "希望发帖页离开前能提醒一下",
        "刚才写东西写到一半，手滑点了别的地方，虽然最后没丢，但那一瞬间还是紧张了一下。\n\n如果发帖页有未保存内容，离开前能弹个提醒就好了。哪怕只是浏览器本地提示，也能让人安心一点。写长帖的时候真的怕误触。",
        ("建议", "发帖"),
    ),
    ArticleSpec(
        "experience",
        "Aki_慢慢来",
        "把待办缩成三件事，焦虑少了",
        "我以前每天早上会写很多待办，写完就开始焦虑。因为看起来一天根本做不完，最后反而拖着不想开始。\n\n现在只写三件最重要的事，做完就算今天没白过。剩下的有空再补。清单短了以后，行动反而容易了。",
        ("经验", "效率"),
    ),
    ArticleSpec(
        "lounge",
        "momo-离线",
        "周末不回工作消息，像偷偷放了个假",
        "上周末我把工作群免打扰打开了，只在晚上固定看一眼。没有完全失联，但不再每条消息都马上点开。\n\n很奇怪，只是少看几次手机，周末就长出来一点。以前休息日总像待命，现在终于像真的休息。",
        ("周末", "休息"),
    ),
    ArticleSpec(
        "qna",
        "kk不在线",
        "大家会怎么处理收藏夹太乱",
        "我的浏览器收藏夹已经乱到自己都不想点开了。教程、工具、文章、想买的东西全混在一起。\n\n我试过分很多文件夹，但过几天又乱。大家有没有比较简单的整理方式？最好是懒人也能坚持的那种。",
        ("求助", "整理"),
    ),
    ArticleSpec(
        "resources",
        "Nate_路过",
        "一个简单的临时记事方法",
        "我现在电脑上常开一个纯文本临时记事页，只放今天会用到的碎片，比如快递单号、会议链接、突然想到的一句话。\n\n它不负责长期保存，晚上就清空。这样反而不会变成第二个收藏夹。临时的东西就让它临时一点，挺省心。",
        ("方法", "工具"),
    ),
    ArticleSpec(
        "reading",
        "小K_再看看",
        "一本书看不进去时，我会先读目录",
        "有些书不是不好，就是一开始很难进。我以前硬读几页读不动就放弃，现在会先翻目录和小标题。\n\n大概知道这本书要讲什么以后，再挑一个最感兴趣的章节开始。这样压力小很多，也不一定非要从第一页读起。",
        ("读书", "方法"),
    ),
    ArticleSpec(
        "health",
        "rain_404",
        "晚饭后走十分钟，比想象中容易坚持",
        "我一直不太能坚持运动，跑步、健身都试过，最后都停了。最近换成晚饭后下楼走十分钟。\n\n因为目标很小，反而没那么抗拒。走完也不会累，但肚子没那么撑，晚上心情也平一点。先别追求厉害，能做下去就不错。",
        ("健康", "散步"),
    ),
    ArticleSpec(
        "lounge",
        "zzZ_醒了",
        "早上提前十分钟出门，路上没那么烦",
        "我不是早起的人，提前十分钟对我来说已经很难了。但这几天试了一下，发现路上火气真的少很多。\n\n不用一路小跑，不用卡着最后一分钟进电梯，等红灯也没那么急。十分钟不多，但能换一点从容。",
        ("通勤", "早起"),
    ),
    ArticleSpec(
        "benefits",
        "beta路人",
        "会员自动续费真的要定期看一眼",
        "今天看账单才发现，一个很久没用的软件还在自动续费。每个月金额不大，所以一直没注意。\n\n我现在准备每个月月底看一次支付记录，尤其是视频、云盘、工具类会员。不是省大钱，但至少别为不用的东西一直付。",
        ("省钱", "会员"),
    ),
    ArticleSpec(
        "feedback",
        "loop_一下",
        "帖子列表能不能有个只看未读",
        "最近帖子多起来以后，我有时候想找自己还没看过的内容，会在列表里来回翻。\n\n如果能有一个“只看未读”的筛选就好了。不是特别复杂的功能，但对经常逛的人应该挺有用，也能少漏掉一些讨论。",
        ("建议", "未读"),
    ),
    ArticleSpec(
        "news",
        "穿猫的靴子",
        "越来越多工具开始强调离线可用",
        "最近看到几个写作和笔记工具都在讲离线可用。以前大家默认一直联网，现在好像又开始重视本地保存。\n\n我挺喜欢这个方向。网络不好时还能写，地铁上也不会卡住。同步可以慢一点，但正在写的东西不能丢。",
        ("趋势", "工具"),
    ),
    ArticleSpec(
        "resources",
        "远山便利店",
        "一个无需注册的截图标注小流程",
        (
            "最近我给家里人远程说明电脑问题，发现最省事的流程不是开会议，"
            "而是截图后直接圈重点。\n\n"
            "我现在一般是：系统截图、在线压缩一下、用浏览器自带标注或临时画板圈出按钮，"
            "再发一张图过去。整个过程不用注册，也不用让对方装新软件。\n\n"
            "适合那种“你点这里，再点这里”的场景。缺点是复杂问题还是讲不清，"
            "但比发一长串文字更不容易误会。"
        ),
        ("工具", "截图", "效率"),
    ),
    ArticleSpec(
        "resources",
        "Nate_路过",
        "我整理资料时会先建一个临时索引",
        (
            "以前我看到资料就直接丢进收藏夹，过一阵再找，"
            "标题全都眼熟但想不起哪个有用。\n\n"
            "最近改成先建一个临时索引：每条只写三列，链接、我为什么存、"
            "下次什么时候可能用。看起来多一步，但后面筛选轻松很多。\n\n"
            "最关键的是“为什么存”这列。如果当时说不清原因，"
            "通常说明它只是让我焦虑，并不是真的需要。"
        ),
        ("资料整理", "方法", "收藏夹"),
    ),
    ArticleSpec(
        "qna",
        "rain_404",
        "想培养长期记录习惯，第一周应该从哪里开始",
        (
            "我一直想养成记录习惯，但每次都是开头两天很认真，第三四天就断了。"
            "之前试过日记、待办、读书笔记，最后都变成空模板。\n\n"
            "这次不想一上来就搞得太复杂，想先坚持一周。"
            "大家觉得第一周应该记录什么最容易继续？是每天一句话，"
            "还是只记发生过的一件小事？\n\n"
            "如果有你们坚持下来的方法，也想听听。"
        ),
        ("求助", "记录", "习惯"),
    ),
    ArticleSpec(
        "qna",
        "kk不在线",
        "做知识卡片时，标签到底要不要分很细",
        (
            "我最近在整理一些读书和工具笔记，遇到一个问题："
            "标签分粗了不好找，分细了又记不住自己建过什么。\n\n"
            "比如一条笔记既可以叫“阅读”，也可以叫“输入”，还可以叫“方法论”。"
            "结果最后标签越来越多，反而不敢写新卡片。\n\n"
            "大家会怎么控制标签数量？是先少量固定标签，还是后期再合并？"
        ),
        ("求助", "标签", "笔记"),
    ),
    ArticleSpec(
        "experience",
        "loop_一下",
        "复盘踩坑时，我现在会先写事实时间线",
        (
            "以前我复盘问题，总是很快跳到“我当时太粗心了”这种结论。"
            "后来发现这样没什么用，下次遇到类似场景还是会重复。\n\n"
            "最近改成先写事实时间线：几点看到现象，查了哪几处，做了什么改动，"
            "哪个动作让结果变化。写完以后，真正的问题通常会自己浮出来。\n\n"
            "它的好处是把情绪先放一边，不急着给自己定性。很多坑不是靠骂自己解决的，"
            "是靠看清楚路径解决的。"
        ),
        ("经验", "复盘", "踩坑"),
    ),
    ArticleSpec(
        "experience",
        "Aki_慢慢来",
        "把个人项目 README 写给三个月后的自己",
        (
            "我有个小项目隔了三个月再打开，第一反应是：这是谁写的，怎么启动来着？\n\n"
            "后来我给 README 加了几块很朴素的内容：项目是干什么的、本地怎么跑、"
            "常见命令、哪些地方暂时不要动。不是给别人看的漂亮文档，"
            "更像给未来自己的提示条。\n\n"
            "现在再切回来，至少不用重新翻聊天记录和命令历史。个人项目也值得留一点路标。"
        ),
        ("经验", "文档", "个人项目"),
    ),
    ArticleSpec(
        "feedback",
        "huai_07",
        "希望标签输入能提示常用写法",
        (
            "刚刚发帖时有点纠结标签应该写“读书方法”还是“读书、方法”两个标签。"
            "不同人写法不一样，后面搜索可能会散掉。\n\n"
            "如果标签输入框能在输入时提示常用标签，或者显示这个版块最近常用的几个词，"
            "应该会更容易统一。\n\n"
            "不一定要强制选择，只要有轻提示就够了，避免新用户一开始就不知道怎么填。"
        ),
        ("建议", "标签", "发帖"),
    ),
    ArticleSpec(
        "feedback",
        "小K_再看看",
        "版块页能不能显示一条新手发帖示例",
        (
            "我点进不同版块时，有时候能理解版块名字，但不确定什么样的内容算合适。"
            "尤其是“经验分享”和“资源荟萃”，边界偶尔会混。\n\n"
            "如果每个版块页能放一条很短的发帖示例，"
            "比如“适合：我如何整理收藏夹”“不适合：只丢一个链接不说明原因”，"
            "可能会更清楚。\n\n"
            "这个示例不用占很大面积，放在发帖按钮附近就行。"
        ),
        ("建议", "版块", "新手"),
    ),
    ArticleSpec(
        "memory-notes",
        "雾里看山",
        "翻到三年前的一句便签，突然有点被提醒",
        (
            "今天清理旧手机备忘录，翻到三年前写的一句话："
            "先把今天过好，不要提前替所有明天焦虑。\n\n"
            "当时应该是工作压力很大的时候写的，具体发生什么已经记不清了。"
            "但这句话现在看还是有用，像隔了很久的自己给我递了一张小纸条。\n\n"
            "我把它搬到这里，算是给这段旧心情找个地方放。"
            "也想问问大家，有没有哪句旧笔记到现在还会提醒你？"
        ),
        ("旧笔记", "金句", "生活片段"),
    ),
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI options for a pending-only persona article seed run."""
    parser = argparse.ArgumentParser(
        description="Seed configured persona-written topic reviewables without publishing them."
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print the plan.")
    parser.add_argument("--seed-key-prefix", default=BATCH_KEY)
    return parser.parse_args(argv)


async def async_main(argv: Sequence[str] | None = None) -> None:
    """Open one database session, seed/reuse reviewables, and print a JSON summary."""
    configure_logging()
    args = parse_args(argv)
    async with AsyncSessionLocal() as session:
        result = await seed_articles(session, args)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


async def seed_articles(session: AsyncSession, args: argparse.Namespace) -> dict[str, object]:
    """Create one pending queued-topic reviewable per configured persona.

    Key side effect: when not in dry-run mode this writes/updates persona users and
    inserts only moderation reviewables; it never approves or publishes topics.
    """
    validate_article_authors()
    legacy_renames = await rename_legacy_personas(session, dry_run=args.dry_run)
    personas = await upsert_personas(session, dry_run=args.dry_run)
    boards = await load_boards(session, ARTICLES)
    if args.dry_run:
        return {
            "dry_run": True,
            "seed_key_prefix": args.seed_key_prefix,
            "mode": "pending_review_only",
            "legacy_renames": legacy_renames,
            **summarize_articles(ARTICLES),
            "personas": [persona.username for persona in PERSONAS],
        }

    created = 0
    reused = 0
    pending = 0
    for index, article in enumerate(ARTICLES, start=1):
        reviewable, is_created = await get_or_create_article_reviewable(
            session,
            article=article,
            board=boards[article.board_slug],
            author=personas[article.author],
            seed_key=f"{args.seed_key_prefix}:topic:{index:02d}",
        )
        created += int(is_created)
        reused += int(not is_created)
        pending += int(reviewable.status == "pending")
    await session.commit()
    return {
        "seed_key_prefix": args.seed_key_prefix,
        "mode": "pending_review_only",
        "legacy_renames": legacy_renames,
        **summarize_articles(ARTICLES),
        "created_reviewables": created,
        "reused_reviewables": reused,
        "pending_reviewables": pending,
        "published_topics": 0,
    }


# Validate that every article references one of the configured persona usernames.
def validate_article_authors() -> None:
    """Fail fast if article authors and persona definitions drift apart."""
    persona_names = {persona.username for persona in PERSONAS}
    missing = [article.author for article in ARTICLES if article.author not in persona_names]
    if missing:
        raise RuntimeError(f"Article author has no persona: {', '.join(missing)}")


# Rename the earlier rejected naming batch so future seeds reuse those accounts.
async def rename_legacy_personas(session: AsyncSession, *, dry_run: bool) -> int:
    """Rename legacy seed accounts to the selected final forum names.

    Key parameters: `dry_run` prevents writes. Return value is the number of
    legacy users that exist and would be/are renamed. Side effect when enabled:
    updates username, email, display name, bio, role, and status for matched users.
    """
    persona_by_name = {persona.username: persona for persona in PERSONAS}
    old_names = [old for old, _new in LEGACY_PERSONA_RENAMES]
    new_names = [new for _old, new in LEGACY_PERSONA_RENAMES]
    target_emails = [persona_by_name[name].email for name in new_names]
    users = list(
        await session.scalars(
            select(User).where(
                or_(User.username.in_(old_names + new_names), User.email.in_(target_emails))
            )
        )
    )
    by_username = {user.username: user for user in users}
    by_email = {user.email: user for user in users}
    rename_count = 0
    for old_name, new_name in LEGACY_PERSONA_RENAMES:
        old_user = by_username.get(old_name)
        if old_user is None:
            continue
        persona = persona_by_name[new_name]
        persona_kind = required_persona_kind(persona)
        existing_name_user = by_username.get(persona.username)
        existing_email_user = by_email.get(persona.email)
        if existing_name_user is not None and existing_name_user.id != old_user.id:
            raise RuntimeError(f"Target username already exists: {persona.username}")
        if existing_email_user is not None and existing_email_user.id != old_user.id:
            raise RuntimeError(f"Target email already exists: {persona.email}")
        rename_count += 1
        if dry_run:
            continue
        old_user.username = persona.username
        old_user.email = persona.email
        old_user.display_name = persona.username
        old_user.bio = persona.bio
        if persona.avatar_url is not None:
            old_user.avatar_url = persona.avatar_url
        old_user.role = "user"
        old_user.status = "active"
        old_user.is_persona = True
        if old_user.persona_kind is None:
            old_user.persona_kind = persona_kind
    if rename_count and not dry_run:
        await session.flush()
    return rename_count


# Ensure the persona accounts exist before reviewables are created for them.
async def upsert_personas(session: AsyncSession, *, dry_run: bool) -> dict[str, User]:
    """Create or refresh persona users and return them keyed by username.

    Key parameter: `dry_run` builds in-memory stand-ins without writing new users.
    Side effect when enabled: inserts missing users and refreshes display/bio/status.
    """
    users: dict[str, User] = {}
    for persona in PERSONAS:
        persona_kind = required_persona_kind(persona)
        existing = await session.scalar(
            select(User).where(or_(User.username == persona.username, User.email == persona.email))
        )
        if existing is not None:
            if existing.username != persona.username or existing.email != persona.email:
                raise RuntimeError(
                    "Persona username/email conflicts with an existing different user: "
                    f"id={existing.id}, username={existing.username}, email={existing.email}"
                )
            if not dry_run:
                existing.display_name = persona.username
                existing.bio = persona.bio
                if persona.avatar_url is not None:
                    existing.avatar_url = persona.avatar_url
                existing.status = "active"
                existing.role = "user"
                existing.is_persona = True
                if existing.persona_kind is None:
                    existing.persona_kind = persona_kind
            users[persona.username] = existing
            continue
        if dry_run:
            users[persona.username] = User(
                username=persona.username,
                email=persona.email,
                hashed_password="dry-run",
                display_name=persona.username,
                bio=persona.bio,
                avatar_url=persona.avatar_url,
                role="user",
                status="active",
                is_persona=True,
                persona_kind=persona_kind,
            )
            continue
        user = User(
            username=persona.username,
            email=persona.email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            display_name=persona.username,
            bio=persona.bio,
            avatar_url=persona.avatar_url,
            role="user",
            status="active",
            is_persona=True,
            persona_kind=persona_kind,
        )
        session.add(user)
        await session.flush()
        users[persona.username] = user
    return users


# Load only public boards used by the article batch.
async def load_boards(session: AsyncSession, articles: Sequence[ArticleSpec]) -> dict[str, Board]:
    """Return public boards keyed by slug for the configured article specs."""
    slugs = sorted({article.board_slug for article in articles})
    boards = list(await session.scalars(select(Board).where(Board.slug.in_(slugs))))
    by_slug = {board.slug: board for board in boards}
    missing = [slug for slug in slugs if slug not in by_slug]
    if missing:
        raise RuntimeError(f"Missing boards: {', '.join(missing)}")
    non_public = [board.slug for board in boards if board.visibility != "public"]
    if non_public:
        raise RuntimeError(f"Persona seed boards must be public: {', '.join(non_public)}")
    return by_slug


# Reuse a reviewable if this seed key has already been queued before.
async def find_reviewable_by_seed_key(session: AsyncSession, seed_key: str) -> Reviewable | None:
    """Find an existing persona/seed reviewable by its idempotency seed key."""
    reviewables = list(
        await session.scalars(
            select(Reviewable).where(Reviewable.source.in_((SOURCE, "seed_content"))).limit(5000)
        )
    )
    return next(
        (reviewable for reviewable in reviewables if reviewable.data.get("seed_key") == seed_key),
        None,
    )


# Create a queued-topic reviewable and intentionally leave it pending.
async def get_or_create_article_reviewable(
    session: AsyncSession,
    *,
    article: ArticleSpec,
    board: Board,
    author: User,
    seed_key: str,
) -> tuple[Reviewable, bool]:
    """Create or reuse the pending reviewable for one article.

    Return value: `(reviewable, created)` where `created` is false on idempotent
    reruns. Side effect: inserts a `queued_topic` reviewable but no public topic.
    """
    existing = await find_reviewable_by_seed_key(session, seed_key)
    if existing is not None:
        return existing, False
    tags = normalized_unique_tags(article.tags)
    ForumService(session)._validate_board_topic_tags(board, tags)
    reviewable = await ModerationService(session).create_content_reviewable(
        current_user=author,
        reviewable_type="queued_topic",
        board=board,
        sanitized_fields={"title": article.title, "raw_md": article.body},
        matched_fields=("persona_seed_requires_review",),
        data={
            "title": article.title,
            "raw_md": article.body,
            "tags": tags,
            "pinned": False,
            "featured": False,
            "board_slug": board.slug,
            "seed_key": seed_key,
            "persona_seed": True,
        },
        source=SOURCE,
        source_summary=SOURCE_SUMMARY,
    )
    return reviewable, True


# Normalize display tags through the same helper used by forum writes.
def normalized_unique_tags(values: Sequence[str]) -> list[str]:
    """Normalize, de-duplicate, and cap article tags before storing review data."""
    tags: list[str] = []
    for value in values:
        tag = normalize_tag_name(value)
        if tag and tag not in tags:
            tags.append(tag[:48])
    return tags[:8]


# Produce a compact JSON-friendly summary for dry-run and actual runs.
def summarize_articles(articles: Sequence[ArticleSpec]) -> dict[str, object]:
    """Count articles by board and return JSON-serializable summary fields."""
    board_counts = Counter(article.board_slug for article in articles)
    return {
        "articles": len(articles),
        "boards": dict(sorted(board_counts.items())),
    }


def main() -> None:
    """CLI entry point for the persona article seed script."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
