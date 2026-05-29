"""新闻源配置和全局常量。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# 项目根目录(src 的父目录)
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BEIJING = ZoneInfo("Asia/Shanghai")

# 输出目录
DATA_DIR = ROOT / "data" / "episodes"
SITE_DIR = ROOT / "site"
AUDIO_DIR = SITE_DIR / "audio"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"

for d in [DATA_DIR, SITE_DIR, AUDIO_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@dataclass
class FeedSource:
    name: str
    url: str
    lang: str  # "zh" / "en"
    weight: int = 1  # 排序权重


# 新闻源列表。weight 越大,排序越靠前。
# 中文源容易失效,RSSHub 镜像也常被限流;多放备用,运行时空源会被自动跳过。
FEED_SOURCES: list[FeedSource] = [
    # ===== 中文 =====
    FeedSource("少数派", "https://sspai.com/feed", "zh", weight=3),
    FeedSource("IT之家", "https://www.ithome.com/rss/", "zh", weight=3),
    FeedSource("爱范儿", "https://www.ifanr.com/feed", "zh", weight=2),
    FeedSource("极客公园", "https://www.geekpark.net/rss", "zh", weight=2),
    FeedSource("品玩", "https://www.pingwest.com/feed", "zh", weight=2),
    FeedSource("钛媒体", "https://www.tmtpost.com/rss.xml", "zh", weight=2),
    FeedSource("量子位", "https://www.qbitai.com/feed", "zh", weight=3),
    FeedSource("机器之心", "https://www.jiqizhixin.com/rss", "zh", weight=3),
    FeedSource("InfoQ 中文", "https://www.infoq.cn/feed.xml", "zh", weight=2),
    FeedSource("36Kr (RSSHub)", "https://rsshub.app/36kr/news/latest", "zh", weight=2),
    FeedSource("36Kr (备用)", "https://rsshub.feeded.xyz/36kr/news/latest", "zh", weight=1),
    FeedSource("虎嗅", "https://www.huxiu.com/rss/0.xml", "zh", weight=1),
    # ===== 英文 =====
    FeedSource("Hacker News", "https://hnrss.org/frontpage", "en", weight=3),
    FeedSource("TechCrunch", "https://techcrunch.com/feed/", "en", weight=2),
    FeedSource("The Verge", "https://www.theverge.com/rss/index.xml", "en", weight=2),
    FeedSource("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "en", weight=2),
    FeedSource("Wired", "https://www.wired.com/feed/rss", "en", weight=2),
    FeedSource("MIT Tech Review", "https://www.technologyreview.com/feed/", "en", weight=3),
    FeedSource("Engadget", "https://www.engadget.com/rss.xml", "en", weight=1),
    FeedSource("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", "en", weight=2),
]


# ===== 摘要 LLM =====
# 现在统一走 OpenAI 兼容接口(mify 的 /v1),支持 Gemini / Claude / DeepSeek 等
# LLM_* 优先,未设则 fallback 到 ANTHROPIC_*(便于复用 shell env)
def _llm_base_fallback() -> str | None:
    """从 ANTHROPIC_BASE_URL 推 OpenAI 兼容端点(/anthropic 后缀替换为 /v1)。"""
    base = os.getenv("ANTHROPIC_BASE_URL", "")
    if not base:
        return None
    if base.rstrip("/").endswith("/anthropic"):
        return base.rstrip("/")[: -len("/anthropic")] + "/v1"
    return base

LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or _llm_base_fallback()
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("ANTHROPIC_MODEL", "vertex_ai/gemini-3.1-pro-preview")

# 兼容老变量名(check.py 等仍在引用)
ANTHROPIC_API_KEY = LLM_API_KEY
ANTHROPIC_BASE_URL = LLM_BASE_URL
ANTHROPIC_MODEL = LLM_MODEL

# ===== TTS =====
# 后端策略:openai / mify / say (macOS 自带,免费 fallback)
TTS_BACKEND = os.getenv("TTS_BACKEND", "openai")  # openai (走 mify) / say (macOS 自带,免费 fallback)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or LLM_API_KEY  # 复用 mify key
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or LLM_BASE_URL
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "xiaomi/tts-multivoice-v1")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "shimmer")

# macOS say voice (中文): Tingting(普通话女) / Sin-ji(粤语) / Mei-Jia(台湾普通话)
SAY_VOICE = os.getenv("SAY_VOICE", "Tingting")
SAY_RATE = int(os.getenv("SAY_RATE", "190"))  # 字/分钟,默认稍快

# 播客元信息
PODCAST = {
    "title": os.getenv("PODCAST_TITLE", "每日科技速读"),
    "author": os.getenv("PODCAST_AUTHOR", "AI 主播"),
    "email": os.getenv("PODCAST_EMAIL", "you@example.com"),
    "description": os.getenv(
        "PODCAST_DESCRIPTION",
        "每天 5 分钟,听完昨天最重要的科技新闻。",
    ),
    "site_url": os.getenv("PODCAST_SITE_URL", "http://localhost:8000"),
    "language": os.getenv("PODCAST_LANGUAGE", "zh-cn"),
}

# R2(阶段 2)
R2 = {
    "account_id": os.getenv("R2_ACCOUNT_ID", ""),
    "access_key": os.getenv("R2_ACCESS_KEY", ""),
    "secret_key": os.getenv("R2_SECRET_KEY", ""),
    "bucket": os.getenv("R2_BUCKET", ""),
    "public_base": os.getenv("R2_PUBLIC_BASE", ""),
}

# 每天最多采纳的新闻条数(防止稿子过长 + 控制 API 成本)
MAX_ITEMS_PER_DAY = 50

# 同一来源在最终列表里的条目上限(防止某一家刷屏)
MAX_ITEMS_PER_SOURCE = 8

# 播客只播报 importance >= PODCAST_MIN_IMPORTANCE 的新闻(其余只在网页展示)
PODCAST_MIN_IMPORTANCE = 3

# TTS 单次最长字符数
TTS_CHUNK_LIMIT = 3500
