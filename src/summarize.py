"""调用 LLM 给新闻做摘要,并合成整体播音稿。

走 mify 的 OpenAI 兼容接口(/v1),模型用 Gemini 3.1 Pro Preview。
模型可通过 LLM_MODEL 环境变量切换(任何 mify 支持的 LLM)。
"""
from __future__ import annotations

import json
import logging
from datetime import date

from openai import OpenAI

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

log = logging.getLogger(__name__)

SYSTEM_PROMPT_DIGEST = """你是一位科技新闻编辑,负责给中国 PM 用户做"昨日科技日报"。

输出要求(严格遵守 JSON):
1. 中文摘要 100-200 字,客观陈述事实,不夸张不情绪化。
2. 三个要点,每个 20-40 字,提炼"发生了什么 / 为什么重要 / 对谁有影响"。
3. 主题分类,从以下选一个:[AI模型, AI产品, 硬件, 创业融资, 互联网平台, 政策监管, 开源工具, 学术研究, 其他]
4. 重要性 1-5(5=必读), 5 给真正影响行业格局的事件,2-3 给一般性更新。

英文新闻翻译成中文摘要,但保留产品/公司/人名的英文原文(如 "OpenAI 发布 GPT-5",不写"开放人工智能")。
"""


SYSTEM_PROMPT_SCRIPT = """你是一位中文播客主播,声音风格干练专业,像"科技早知道"那样。

任务:把若干条新闻编排成 5-8 分钟的口播稿,听众是中国互联网/AI 从业者。

写作规范:
- 开头一句问候 + 当天日期(用"五月二十六日"这种汉字,不写阿拉伯数字)
- 按主题聚类播报(AI / 硬件 / 创业 / 政策),每个主题间用过渡句
- 每条新闻 30-60 秒(约 80-150 字),先一句结论再展开
- 英文产品名/公司名保留英文(GPT-5 / NVIDIA),让 TTS 按英文读
- 数字用汉字("二零二六年"而非"2026 年","一百亿美元"而非"100 亿美元"),读起来更自然
- 句子要短,每句不超过 30 字,多用句号
- 结尾一句总结+告别("以上就是今天的内容,我们明天见")

输出纯文本,不要 markdown 格式,不要 emoji,不要"【】"等符号。
"""


def _client() -> OpenAI:
    return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


def _chunk(items: list[dict], size: int) -> list[list[dict]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _strip_code_fence(text: str) -> str:
    """模型偶尔会把 JSON 包在 ```json ... ``` 里,剥掉。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


def summarize_items(items: list[dict]) -> list[dict]:
    """给每条新闻补 ai_summary / ai_points / topic / importance 字段。批量请求。"""
    client = _client()
    out: list[dict] = []
    for batch in _chunk(items, 8):
        user_payload = [
            {
                "id": it["id"],
                "source": it["source"],
                "lang": it["lang"],
                "title": it["title"],
                "summary": it["summary_raw"],
            }
            for it in batch
        ]
        prompt = (
            "下面是 RSS 源抓到的若干条新闻,逐条产出 JSON 数组,每个元素含字段:\n"
            "id, summary(中文摘要), points(数组,3 条要点), topic, importance(1-5)\n"
            "只返回 JSON 数组,不要任何前言/后缀/代码块标记。\n\n"
            f"输入:\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}"
        )
        log.info("summarize batch of %d (model=%s)", len(batch), LLM_MODEL)
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            max_tokens=4000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_DIGEST},
                {"role": "user", "content": prompt},
            ],
        )
        text = _strip_code_fence(resp.choices[0].message.content or "")
        try:
            results = json.loads(text)
        except json.JSONDecodeError:
            log.warning("JSON parse failed, raw response (first 500):\n%s", text[:500])
            continue
        by_id = {r["id"]: r for r in results if isinstance(r, dict) and "id" in r}
        for it in batch:
            ai = by_id.get(it["id"], {})
            it["ai_summary"] = ai.get("summary", it["summary_raw"][:200])
            it["ai_points"] = ai.get("points", [])
            it["topic"] = ai.get("topic", "其他")
            it["importance"] = int(ai.get("importance", 3) or 3)
            out.append(it)
    return out


def build_podcast_script(items: list[dict], target_date: date) -> str:
    """把摘要好的新闻条目编排成播音稿。"""
    client = _client()
    grouped: dict[str, list[dict]] = {}
    for it in sorted(items, key=lambda x: (-x["importance"], x["topic"])):
        grouped.setdefault(it["topic"], []).append(it)
    digest_text = ""
    for topic, lst in grouped.items():
        digest_text += f"\n## {topic}\n"
        for it in lst:
            digest_text += f"- [{it['source']}] {it['title']}\n  摘要:{it['ai_summary']}\n"
    prompt = (
        f"日期:{target_date.strftime('%Y-%m-%d')}\n\n"
        f"以下是当日摘要,请按规范写成 5-8 分钟的口播稿:\n{digest_text}"
    )
    log.info("build script (%d items, %d topics, model=%s)", len(items), len(grouped), LLM_MODEL)
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=6000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_SCRIPT},
            {"role": "user", "content": prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()
