"""把当期内容推送到飞书群机器人。

群机器人的安全设置必须勾"关键词"=科技速读(消息里要含此字)。
卡片格式: https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/feishu-cards/getting-started/template-cards
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

import requests

from .config import FEISHU_BOT_WEBHOOK, PODCAST

log = logging.getLogger(__name__)


def _build_card(ep: dict, site_url: str) -> dict[str, Any]:
    items = ep.get("items", [])
    date_pretty = _date_to_pretty(ep["date"])
    weekday = _weekday(ep["date"])
    duration = ep.get("duration_min", 0)

    # 主题分布
    topic_counter = Counter(it.get("topic", "其他") for it in items)
    topic_lines = "\n".join(
        f"  • {t} ({c})" for t, c in topic_counter.most_common(8)
    )

    # 头条:重要性最高的 1-3 条
    sorted_items = sorted(items, key=lambda x: -x.get("importance", 3))
    headlines = sorted_items[:3]
    headline_lines = "\n\n".join(
        f"**{i+1}.** {h['title']}\n{_truncate(h.get('ai_summary', ''), 80)}"
        for i, h in enumerate(headlines)
    )

    episode_url = f"{site_url}/episodes/{ep['date']}.html"
    audio_url = ep.get("audio_url") or ""

    actions = [
        {
            "tag": "button",
            "text": {"tag": "plain_text", "content": "🌐 打开网页阅读"},
            "url": episode_url,
            "type": "primary",
        }
    ]
    if audio_url:
        actions.append(
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "🎧 直接听播客"},
                "url": audio_url,
                "type": "default",
            }
        )

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📡 每日科技速读 · {date_pretty}",
                },
                "template": "orange",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**{weekday}** · "
                            f"**{len(items)}** 条新闻 · "
                            f"**{len(topic_counter)}** 个主题 · "
                            f"约 **{duration}** 分钟"
                        ),
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**🔥 头条**\n\n{headline_lines}",
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📋 主题分布**\n{topic_lines}",
                    },
                },
                {"tag": "action", "actions": actions},
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"AI 自动生成 · {PODCAST['author']}",
                        }
                    ],
                },
            ],
        },
    }


def push_episode(ep: dict, site_url: str | None = None) -> bool:
    """推送一期到飞书群。返回是否成功。未配置 webhook 时跳过。"""
    if not FEISHU_BOT_WEBHOOK:
        log.info("FEISHU_BOT_WEBHOOK 未配置,跳过推送")
        return False
    site_url = (site_url or PODCAST.get("site_url", "")).rstrip("/")
    payload = _build_card(ep, site_url)
    try:
        r = requests.post(FEISHU_BOT_WEBHOOK, json=payload, timeout=10)
        data = r.json()
    except Exception as e:
        log.error("飞书推送失败: %s", e)
        return False
    if data.get("StatusCode") == 0 or data.get("code") == 0:
        log.info("✓ 飞书推送成功 (group bot)")
        return True
    log.error("飞书推送返回非 0: %s", data)
    return False


def _truncate(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _date_to_pretty(d: str) -> str:
    """'2026-06-01' -> '6月1日'"""
    from datetime import datetime
    dt = datetime.strptime(d, "%Y-%m-%d")
    return f"{dt.month}月{dt.day}日"


def _weekday(d: str) -> str:
    from datetime import datetime
    dt = datetime.strptime(d, "%Y-%m-%d")
    return ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][dt.weekday()]


if __name__ == "__main__":
    # 命令行用法: python -m src.push_feishu [date]
    # date 默认最新一期
    import json
    import sys
    from pathlib import Path
    from .config import DATA_DIR, PODCAST

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) > 1:
        target = sys.argv[1]
        f = DATA_DIR / f"{target}.json"
    else:
        files = sorted(DATA_DIR.glob("*.json"), reverse=True)
        if not files:
            print("no episodes found")
            sys.exit(1)
        f = files[0]

    ep = json.loads(Path(f).read_text(encoding="utf-8"))
    ok = push_episode(ep)
    sys.exit(0 if ok else 1)
