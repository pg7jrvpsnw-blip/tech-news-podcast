"""生成 iTunes 兼容的 podcast RSS feed。"""
from __future__ import annotations

import json
import logging
from datetime import datetime, time
from pathlib import Path

from feedgen.feed import FeedGenerator

from .config import BEIJING, DATA_DIR, PODCAST, SITE_DIR

log = logging.getLogger(__name__)


def _all_episodes() -> list[dict]:
    out = []
    for f in sorted(DATA_DIR.glob("*.json"), reverse=True):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return out


def build_feed() -> Path:
    fg = FeedGenerator()
    fg.load_extension("podcast")

    site_url = PODCAST["site_url"].rstrip("/")
    fg.id(site_url + "/")
    fg.title(PODCAST["title"])
    fg.author({"name": PODCAST["author"], "email": PODCAST["email"]})
    fg.link(href=site_url, rel="alternate")
    fg.link(href=f"{site_url}/feed.xml", rel="self")
    fg.language(PODCAST["language"])
    fg.description(PODCAST["description"])
    fg.image(f"{site_url}/static/cover.png")

    fg.podcast.itunes_category("Technology")
    fg.podcast.itunes_explicit("no")
    fg.podcast.itunes_author(PODCAST["author"])
    fg.podcast.itunes_summary(PODCAST["description"])
    fg.podcast.itunes_image(f"{site_url}/static/cover.png")
    fg.podcast.itunes_owner(name=PODCAST["author"], email=PODCAST["email"])

    episodes = _all_episodes()
    added = 0
    for ep in episodes:
        if not ep.get("audio_url"):
            continue
        added += 1
        fe = fg.add_entry()
        fe.id(ep["audio_url"])  # 用 audio URL 作为稳定 GUID
        fe.title(f"{ep['date']} 科技日报")
        fe.description(_episode_description(ep))
        fe.link(href=f"{site_url}/episodes/{ep['date']}.html")
        # 北京时间 8:00 作为发布时间(让播客 App 排序对)
        pub_dt = datetime.combine(
            datetime.strptime(ep["date"], "%Y-%m-%d").date(),
            time(8, 0),
            tzinfo=BEIJING,
        )
        fe.published(pub_dt)
        fe.enclosure(
            url=ep["audio_url"],
            length=str(ep.get("audio_size_bytes", 0)),
            type="audio/mpeg",
        )
        if ep.get("duration_seconds"):
            fe.podcast.itunes_duration(ep["duration_seconds"])
        fe.podcast.itunes_summary(ep.get("script", "")[:3000])

    out = SITE_DIR / "feed.xml"
    fg.rss_file(str(out), pretty=True)
    log.info("RSS feed -> %s (%d entries with audio, of %d total)", out, added, len(episodes))
    return out


def _episode_description(ep: dict) -> str:
    lines = [f"共收录 {len(ep['items'])} 条科技新闻。"]
    by_topic: dict[str, list[str]] = {}
    for it in ep["items"]:
        by_topic.setdefault(it.get("topic", "其他"), []).append(it["title"])
    for topic, titles in by_topic.items():
        lines.append(f"\n【{topic}】")
        for t in titles[:5]:
            lines.append(f"· {t}")
    return "\n".join(lines)
