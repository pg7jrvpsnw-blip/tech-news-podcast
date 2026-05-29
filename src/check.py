"""配置体检:在跑 make run 之前快速确认环境就绪。

检查项:
- .env 必需字段是否填好
- ffmpeg 是否在 PATH
- Claude API 能否真实调用(发一个最小请求)
- OpenAI TTS 能否真实调用(合成 1 秒空白音频)
- R2 凭证是否能列 bucket(可选,未配则跳过)
- RSS 源活性(可选,跑一次抓取看结果)

使用: python -m src.check  或  make check
"""
from __future__ import annotations

import shutil
import sys
from typing import Callable

from . import config


# ANSI 颜色
G = "\033[92m"  # 绿
Y = "\033[93m"  # 黄
R = "\033[91m"  # 红
DIM = "\033[2m"
END = "\033[0m"


def _ok(msg: str) -> None:
    print(f"  {G}✓{END} {msg}")


def _warn(msg: str) -> None:
    print(f"  {Y}!{END} {msg}")


def _fail(msg: str) -> None:
    print(f"  {R}✗{END} {msg}")


def _section(title: str) -> None:
    print(f"\n{title}")
    print(DIM + "─" * 60 + END)


def check_env() -> bool:
    """必需 env 字段是否填了非占位值。"""
    _section("1. 环境变量")
    must = {
        "LLM_API_KEY": config.LLM_API_KEY,
    }
    bad = False
    for name, val in must.items():
        if not val or val.startswith("sk-xxx") or val == "":
            _fail(f"{name} 未填(或仍是占位 sk-xxx)")
            bad = True
        else:
            masked = val[:7] + "…" + val[-4:] if len(val) > 12 else "***"
            _ok(f"{name} = {masked}")

    optional = {
        "LLM_BASE_URL": config.LLM_BASE_URL or "(空)",
        "LLM_MODEL": config.LLM_MODEL,
        "TTS_BACKEND": config.TTS_BACKEND,
        "OPENAI_TTS_MODEL": config.OPENAI_TTS_MODEL,
        "OPENAI_TTS_VOICE": config.OPENAI_TTS_VOICE,
    }
    for name, val in optional.items():
        _ok(f"{name} = {val}")
    return not bad


def check_ffmpeg() -> bool:
    _section("2. 系统依赖")
    if shutil.which("ffmpeg"):
        _ok("ffmpeg 已安装")
        return True
    _fail("ffmpeg 不在 PATH(brew install ffmpeg)")
    return False


def check_llm() -> bool:
    _section("3. 摘要 LLM 连通性")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
        resp = client.chat.completions.create(
            model=config.LLM_MODEL,
            max_tokens=20,
            messages=[{"role": "user", "content": "回复一个字:好"}],
        )
        text = (resp.choices[0].message.content or "").strip()
        _ok(f"LLM 回复: '{text}' (model={config.LLM_MODEL})")
        if config.LLM_BASE_URL:
            _ok(f"端点: {config.LLM_BASE_URL}")
        return True
    except Exception as e:
        msg = str(e)[:200]
        _fail(f"LLM 调用失败: {type(e).__name__}: {msg}")
        if "Not supported model" in msg:
            _warn(f"这个 key 没有 {config.LLM_MODEL} 的权限,去 https://llm.mioffice.cn/apikey 申请或换模型")
        return False


def check_tts() -> bool:
    _section(f"4. TTS 连通性 (backend={config.TTS_BACKEND})")
    if config.TTS_BACKEND == "say":
        if shutil.which("say"):
            _ok("macOS say 可用(免费 fallback,音质机械但能用)")
            return True
        _fail("backend=say 但系统没有 say 命令(macOS 才有)")
        return False
    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL)
        with client.audio.speech.with_streaming_response.create(
            model=config.OPENAI_TTS_MODEL,
            voice=config.OPENAI_TTS_VOICE,
            input="测试",
            response_format="mp3",
        ) as resp:
            data = resp.read()
        if len(data) < 100:
            _fail(f"返回数据异常({len(data)} bytes)")
            return False
        _ok(f"TTS 合成 OK ({len(data):,} bytes, model={config.OPENAI_TTS_MODEL}, voice={config.OPENAI_TTS_VOICE})")
        return True
    except Exception as e:
        msg = str(e)[:200]
        _fail(f"TTS 调用失败: {type(e).__name__}: {msg}")
        if "Not supported model" in msg:
            _warn(f"这个 key 没有 {config.OPENAI_TTS_MODEL} 权限。可改 .env 的 TTS_BACKEND=say 用 macOS 内置")
        return False


def check_r2() -> bool:
    _section("5. Cloudflare R2 (可选)")
    from .upload import is_configured

    if not is_configured():
        _warn("R2 未配置,跳过(本地开发不需要;部署前再填)")
        return True
    try:
        from .upload import _client

        s3 = _client()
        # 列 bucket 内对象,不需要写权限
        s3.list_objects_v2(Bucket=config.R2["bucket"], MaxKeys=1)
        _ok(f"R2 bucket '{config.R2['bucket']}' 可访问")
        _ok(f"公开域名: {config.R2['public_base']}")
        return True
    except Exception as e:
        _fail(f"R2 访问失败: {type(e).__name__}: {e}")
        return False


def check_rss(quick: bool = True) -> bool:
    _section("6. RSS 源活性 (轻量探测,不下整篇)")
    if quick:
        _warn("跳过(加 --rss 参数会真跑一次 fetch)")
        return True
    try:
        from .fetch import fetch_yesterday

        items = fetch_yesterday()
        sources = {}
        for it in items:
            sources[it["source"]] = sources.get(it["source"], 0) + 1
        _ok(f"抓到 {len(items)} 条新闻,来自 {len(sources)} 个源:")
        for src, n in sorted(sources.items(), key=lambda x: -x[1]):
            print(f"      {src}: {n}")
        if not items:
            _fail("0 条!可能时区或源都失效了")
            return False
        return True
    except Exception as e:
        _fail(f"fetch 失败: {e}")
        return False


def main() -> int:
    print(f"{DIM}科技日报 — 配置体检{END}")
    rss_full = "--rss" in sys.argv

    checks: list[Callable[[], bool]] = [
        check_env,
        check_ffmpeg,
        check_llm,
        check_tts,
        check_r2,
        lambda: check_rss(quick=not rss_full),
    ]

    results = []
    for fn in checks:
        try:
            results.append(fn())
        except Exception as e:
            print(f"  {R}✗ 检查崩了: {e}{END}")
            results.append(False)

    print()
    print(DIM + "─" * 60 + END)
    passed = sum(results)
    total = len(results)
    if passed == total:
        print(f"{G}全部通过 ({passed}/{total}) — 可以 make run 了{END}")
        return 0
    else:
        print(f"{R}失败 {total - passed}/{total} 项 — 修好上面 ✗ 的再跑{END}")
        if not rss_full:
            print(f"{DIM}提示: 跑 'make check-full' 会一并验证 RSS 源{END}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
