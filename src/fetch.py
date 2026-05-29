"""抓取 RSS 源,按"昨天 北京时间"过滤,去重输出。"""
from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time, timedelta
from typing import Any

import feedparser
from dateutil import parser as date_parser

from .config import (
    BEIJING,
    FEED_SOURCES,
    MAX_ITEMS_PER_DAY,
    MAX_ITEMS_PER_SOURCE,
    FeedSource,
)

log = logging.getLogger(__name__)


def _id_for(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _entry_published(entry: Any) -> datetime | None:
    """RSS 条目里发布时间字段不统一,逐个尝试。"""
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if not val:
            continue
        try:
            dt = date_parser.parse(val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=BEIJING)
            return dt.astimezone(BEIJING)
        except (ValueError, TypeError):
            continue
    return None


def _fetch_one(source: FeedSource) -> list[dict]:
    log.info("fetch %s …", source.name)
    try:
        parsed = feedparser.parse(source.url)
    except Exception as e:
        log.warning("source %s failed: %s", source.name, e)
        return []
    items: list[dict] = []
    for entry in parsed.entries:
        link = entry.get("link", "")
        title = entry.get("title", "").strip()
        if not link or not title:
            continue
        published = _entry_published(entry)
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        items.append(
            {
                "id": _id_for(link),
                "source": source.name,
                "lang": source.lang,
                "weight": source.weight,
                "title": title,
                "link": link,
                "published": published.isoformat() if published else None,
                "summary_raw": summary[:1500],  # 截断,防超长
            }
        )
    log.info("source %s -> %d entries", source.name, len(items))
    return items


def _within_target_day(item: dict, target: date) -> bool:
    """目标日期是北京时间的某一天。"""
    if not item["published"]:
        return False
    dt = datetime.fromisoformat(item["published"]).astimezone(BEIJING)
    start = datetime.combine(target, time.min, tzinfo=BEIJING)
    end = start + timedelta(days=1)
    return start <= dt < end


def fetch_yesterday(target_date: date | None = None) -> list[dict]:
    """抓所有源,过滤到目标日期(默认北京时间昨天),去重排序。"""
    if target_date is None:
        target_date = (datetime.now(BEIJING) - timedelta(days=1)).date()
    log.info("target date (Beijing): %s", target_date)

    all_items: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(_fetch_one, s) for s in FEED_SOURCES]
        for f in as_completed(futures):
            all_items.extend(f.result())

    # 过滤日期
    filtered = [it for it in all_items if _within_target_day(it, target_date)]
    log.info("after date filter: %d items", len(filtered))

    # 去重(按 link)
    seen: set[str] = set()
    unique: list[dict] = []
    for it in filtered:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        unique.append(it)

    # 排序:权重降序,然后按发布时间倒序
    unique.sort(key=lambda x: (-x["weight"], -_ts(x["published"])))

    # 单源限流:避免某家刷屏
    per_source: dict[str, int] = {}
    capped: list[dict] = []
    for it in unique:
        n = per_source.get(it["source"], 0)
        if n >= MAX_ITEMS_PER_SOURCE:
            continue
        per_source[it["source"]] = n + 1
        capped.append(it)
    if len(capped) < len(unique):
        log.info("source cap: %d -> %d", len(unique), len(capped))

    if len(capped) > MAX_ITEMS_PER_DAY:
        log.info("truncate to top %d", MAX_ITEMS_PER_DAY)
        capped = capped[:MAX_ITEMS_PER_DAY]
    return capped


def _ts(iso: str | None) -> float:
    if not iso:
        return 0.0
    try:
        return datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return 0.0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    items = fetch_yesterday()
    print(f"\n{len(items)} items")
    for it in items[:10]:
        print(f"[{it['source']}/{it['lang']}] {it['title'][:60]}")
