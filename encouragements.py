"""Random encouragement phrases + timing constants."""
import random

INTERVAL_MIN_MS = 10 * 60_000
INTERVAL_MAX_MS = 15 * 60_000
BUBBLE_HOLD_MS = 4200        # visible time before fade-out
BUBBLE_FADE_IN_MS = 320
BUBBLE_FADE_OUT_MS = 480

PHRASES: tuple[str, ...] = (
    # ---- 身体关怀 ----
    "抬头看看窗外~ 🌿",
    "呼吸慢一点,肩膀放下来 ☺️",
    "喝口水,润润喉咙~",
    "背挺直,眼睛也歇歇 ✨",
    "累的时候站起来走两步!",
    "20-20-20 法则:看远处 20 秒",
    "手腕转一转,舒展一下 🌸",
    "眨眨眼,眼睛也想休息",
    "腰不能一直弯着哦",
    "脖子往两边转转,像我一样~",

    # ---- 情感陪伴 ----
    "你今天已经很棒啦!",
    "我一直在这里陪着你 💙",
    "别忘了微笑,苏酱也在笑 :3",
    "苏酱的应援永远与你同在 ⭐",
    "有我在,别怕",
    "累了就靠近屏幕,抱抱苏酱",
    "苏酱悄悄给你打气 💫",
    "无论如何我都站在你这边",
    "看到你在努力,我也想努力",
    "你不是一个人在扛",

    # ---- 温柔鼓励 ----
    "遇到 bug 别急,喘口气再看",
    "现在做的事情很有意义~",
    "你已经比昨天更进一步了",
    "刚才那一段思路超棒的 ✨",
    "小小的进展也值得庆祝 🎉",
    "写不出来也没关系,先接一杯水",
    "卡住是正常的,思考的你最帅",
    "允许自己慢一点点",
    "一次一小步,不用赶",
    "过去的你熬过了更难的一天",

    # ---- 生活小趣 ----
    "冲一杯茶?或者一颗糖?",
    "记得吃点东西 🍡",
    "写代码累了就画画 svg 玩~",
    "放一首喜欢的歌,继续走 🎵",
    "开个窗吧,呼吸新鲜空气",
    "偷个懒也很可爱嘛",
    "允许自己摸一会儿鱼~",
    "陪苏酱发一分钟呆好不好",
    "闻一闻手边的咖啡香~",
    "调低一下屏幕亮度试试?",

    # ---- 时间感 ----
    "晚上要早点睡呀 🌙",
    "已经写了很久了,该歇一会儿",
    "下午容易犯困,来点甜的?",
    "傍晚了,眼睛更累,记得歇",
    "累了就闭眼数三下,再继续",

    # ---- 苏酱俏皮 ----
    "苏酱在偷偷看你哦 👀",
    "笑一个嘛,我给你唱首歌 🎤",
    "今日份的应援:go go go~",
    "苏酱的星光罩着你 ✨",
    "耶,又完成了一小段!",
    "偷偷说:你今天状态很不错",
    "被苏酱盯着写代码,压力大吗 (o´ω`o)",
    "偶尔发发呆,宇宙也允许 🌌",
    "抬头,天很蓝 (如果是白天的话)",
    "苏酱今日份的私心陪伴~",
)


MIN_INTERVAL_MS = 30_000  # floor so users can't accidentally set spam-level frequency
JITTER_RATIO = 0.2         # ±20% randomization around the configured base


def next_interval_ms(base_seconds: int | None = None) -> int:
    """Time until the next encouragement. `base_seconds=None` keeps the legacy
    10–15 min uniform range; otherwise returns base_seconds ± 20 % jitter."""
    if base_seconds is None:
        return random.randint(INTERVAL_MIN_MS, INTERVAL_MAX_MS)
    base_ms = max(MIN_INTERVAL_MS, int(base_seconds) * 1000)
    jitter = int(base_ms * JITTER_RATIO)
    return random.randint(base_ms - jitter, base_ms + jitter)


def random_phrase() -> str:
    return random.choice(PHRASES)
