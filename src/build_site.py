"""渲染静态网站(首页 + 期目页 + 归档)。"""
from __future__ import annotations

import json
import logging
import shutil
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import (
    DATA_DIR,
    PODCAST,
    SITE_DIR,
    STATIC_DIR,
    TEMPLATES_DIR,
)

log = logging.getLogger(__name__)

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _all_episodes() -> list[dict]:
    out = []
    for f in sorted(DATA_DIR.glob("*.json"), reverse=True):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return out


def _date_parts(d_str: str) -> tuple[str, str]:
    """'2026-05-26' → ('5月26日', '周一')"""
    d = datetime.strptime(d_str, "%Y-%m-%d").date()
    pretty = f"{d.month}月{d.day}日"
    weekday = WEEKDAYS[d.weekday()]
    return pretty, weekday


def _enrich(ep: dict) -> dict:
    """补足模板需要的衍生字段。"""
    items = ep.get("items", [])
    by_topic: dict[str, list[dict]] = {}
    for it in sorted(items, key=lambda x: -x.get("importance", 3)):
        by_topic.setdefault(it.get("topic", "其他"), []).append(it)
    pretty, weekday = _date_parts(ep["date"])
    # 引言:从播音稿前 60 字抽取(去掉问候语)
    script = ep.get("script", "")
    lead = ""
    if script:
        # 跳过第一段问候,取第二段开头
        paragraphs = [p for p in script.split("\n") if p.strip()]
        if len(paragraphs) >= 2:
            lead = paragraphs[1][:80].strip().rstrip("。") + "…"
        else:
            lead = paragraphs[0][:80].strip().rstrip("。") + "…"
    return {
        **ep,
        "by_topic": by_topic,
        "date_pretty": pretty,
        "weekday": weekday,
        "topic_count": len(by_topic),
        "lead": lead,
    }


def _render_episode(env: Environment, ep_view: dict) -> None:
    tpl = env.get_template("episode.html")
    out_dir = SITE_DIR / "episodes"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{ep_view['date']}.html").write_text(
        tpl.render(episode=ep_view, podcast=PODCAST), encoding="utf-8"
    )


def _render_index(env: Environment, ep_view: dict) -> None:
    tpl = env.get_template("episode.html")
    (SITE_DIR / "index.html").write_text(
        tpl.render(episode=ep_view, podcast=PODCAST), encoding="utf-8"
    )


def _render_archive(env: Environment, episodes: list[dict]) -> None:
    items = []
    for ep in episodes:
        pretty, _ = _date_parts(ep["date"])
        items.append(
            {
                "date": ep["date"],
                "date_pretty": pretty,
                "count": len(ep.get("items", [])),
                "duration_min": ep.get("duration_min") or "—",
            }
        )
    tpl = env.get_template("archive.html")
    (SITE_DIR / "archive.html").write_text(
        tpl.render(episodes=items, podcast=PODCAST), encoding="utf-8"
    )


def _copy_static() -> None:
    dst = SITE_DIR / "static"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(STATIC_DIR, dst)


def build_site() -> None:
    episodes = _all_episodes()
    if not episodes:
        log.warning("no episode JSON found, skip build_site")
        return
    env = _env()
    enriched = [_enrich(ep) for ep in episodes]
    for ep_view in enriched:
        _render_episode(env, ep_view)
    _render_index(env, enriched[0])
    _render_archive(env, episodes)
    _copy_static()
    log.info("site rendered: %d episodes -> %s", len(episodes), SITE_DIR)
