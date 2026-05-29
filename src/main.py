"""主编排:抓取 → 总结 → TTS → 生成站点。"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from .build_feed import build_feed
from .build_site import build_site
from .config import AUDIO_DIR, BEIJING, DATA_DIR, PODCAST, SITE_DIR
from .fetch import fetch_yesterday
from .summarize import build_podcast_script, summarize_items
from .tts import get_duration_seconds, synthesize
from .upload import is_configured as r2_configured
from .upload import upload_mp3


def _parse_date(s: str | None) -> date:
    if s:
        return datetime.strptime(s, "%Y-%m-%d").date()
    return (datetime.now(BEIJING) - timedelta(days=1)).date()


def run(target_date: date, skip_tts: bool = False) -> None:
    log = logging.getLogger("main")
    log.info("=== run for %s (skip_tts=%s) ===", target_date, skip_tts)

    # 1. 抓
    items = fetch_yesterday(target_date)
    if not items:
        log.warning("no items for %s, abort", target_date)
        return

    # 2. 摘要 + 分类
    items = summarize_items(items)

    # 3. 编排播音稿
    script = build_podcast_script(items, target_date)
    log.info("script length: %d chars", len(script))

    # 4. TTS
    audio_url = ""
    duration_sec = 0
    audio_size = 0
    if not skip_tts:
        mp3_path = AUDIO_DIR / f"{target_date.isoformat()}.mp3"
        synthesize(script, mp3_path)
        duration_sec = get_duration_seconds(mp3_path)
        audio_size = mp3_path.stat().st_size
        # 配置了 R2 走云端;否则本地路径(适合本地开发)
        key = f"episodes/{target_date.isoformat()}.mp3"
        audio_url = upload_mp3(mp3_path, key)
        if r2_configured():
            log.info("audio public URL: %s", audio_url)
        else:
            log.info("audio (local): %s", audio_url)

    # 5. 写 episode JSON
    ep_data = {
        "date": target_date.isoformat(),
        "generated_at": datetime.now(BEIJING).isoformat(),
        "items": items,
        "script": script,
        "audio_url": audio_url,
        "audio_size_bytes": audio_size,
        "duration_seconds": duration_sec,
        "duration_min": round(duration_sec / 60) if duration_sec else 0,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / f"{target_date.isoformat()}.json").write_text(
        json.dumps(ep_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("episode JSON written")

    # 6. 渲染站点
    build_site()
    build_feed()
    log.info("done. open file://%s/index.html", SITE_DIR)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成科技日报播客")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="目标日期 YYYY-MM-DD (默认北京时间昨天)",
    )
    parser.add_argument(
        "--skip-tts",
        action="store_true",
        help="跳过 TTS 合成(只生成 HTML,省 API 钱)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="只重新渲染站点,不抓不总结不合成",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if args.rebuild:
        build_site()
        build_feed()
        return

    target = _parse_date(args.date)
    run(target, skip_tts=args.skip_tts)


if __name__ == "__main__":
    main()
