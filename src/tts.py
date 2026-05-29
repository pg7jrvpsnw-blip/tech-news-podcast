"""把播音稿调 TTS 合成 mp3。长稿分段后用 pydub 拼接。

后端走 mify(OpenAI 兼容)的 xiaomi/tts-multivoice-v1。
mify 暂未开通 TTS 时,可在 .env 设 TTS_BACKEND=say 用 macOS 自带 say(免费 fallback)。
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path

from openai import OpenAI
from pydub import AudioSegment

from .config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_TTS_MODEL,
    OPENAI_TTS_VOICE,
    SAY_RATE,
    SAY_VOICE,
    TTS_BACKEND,
    TTS_CHUNK_LIMIT,
)

log = logging.getLogger(__name__)


def _client() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


def _split(script: str, limit: int = TTS_CHUNK_LIMIT) -> list[str]:
    """按段落+句号尽量自然地切分,单段不超过 limit 字符。"""
    paragraphs = [p.strip() for p in script.split("\n") if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paragraphs:
        if len(cur) + len(p) + 1 <= limit:
            cur = (cur + "\n" + p).strip()
            continue
        if cur:
            chunks.append(cur)
            cur = ""
        if len(p) > limit:
            sentences = re.split(r"(?<=[。;;!?])", p)
            buf = ""
            for s in sentences:
                if len(buf) + len(s) > limit:
                    if buf:
                        chunks.append(buf)
                    buf = s
                else:
                    buf += s
            if buf:
                cur = buf
        else:
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


def _decode_mify_sse(raw: bytes) -> bytes:
    """mify TTS 用自定义 SSE 流返回 base64 编码的 mp3 chunk。
    格式: 每行 `data:{"audio":"<base64>"}`,最后一行带 `usage` 和 `type:speech.audio.done`。
    """
    chunks: list[bytes] = []
    duration = 0.0
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if "audio" in obj:
            chunks.append(base64.b64decode(obj["audio"]))
        elif obj.get("type") == "speech.audio.done":
            duration = (obj.get("usage") or {}).get("output_audio_duration", 0)
    if duration:
        log.debug("  (mify reported %.1fs audio)", duration)
    return b"".join(chunks)


def _synth_chunk_openai(text: str) -> bytes:
    """单段调 OpenAI 兼容 TTS,返回 mp3 字节。

    OpenAI 官方:返回原始 mp3 二进制
    mify(xiaomi/tts-multivoice-v1):返回 SSE 流,需解码 + base64 拼接
    """
    client = _client()
    with client.audio.speech.with_streaming_response.create(
        model=OPENAI_TTS_MODEL,
        voice=OPENAI_TTS_VOICE,
        input=text,
        response_format="mp3",
    ) as resp:
        raw = resp.read()
    # 检测 mify SSE 格式
    if raw[:5] == b"data:":
        return _decode_mify_sse(raw)
    return raw


def _synth_chunk_say(text: str) -> bytes:
    """用 macOS 自带 say 命令合成,转 mp3 返回字节。"""
    with tempfile.TemporaryDirectory() as td:
        aiff = Path(td) / "out.aiff"
        subprocess.run(
            ["say", "-v", SAY_VOICE, "-r", str(SAY_RATE), "-o", str(aiff), text],
            check=True,
        )
        seg = AudioSegment.from_file(aiff)
        buf = io.BytesIO()
        seg.export(buf, format="mp3", bitrate="96k")
        return buf.getvalue()


def _synth_chunk(text: str) -> bytes:
    if TTS_BACKEND == "say":
        return _synth_chunk_say(text)
    return _synth_chunk_openai(text)


def synthesize(script: str, out_path: Path) -> Path:
    """合成 mp3 写到 out_path。返回路径(便于链式)。"""
    chunks = _split(script)
    log.info(
        "TTS backend=%s, %d chunks (total %d chars) -> %s",
        TTS_BACKEND,
        len(chunks),
        len(script),
        out_path,
    )
    if TTS_BACKEND not in ("say",):
        log.info("  model=%s voice=%s", OPENAI_TTS_MODEL, OPENAI_TTS_VOICE)

    combined = AudioSegment.silent(duration=0)
    for i, chunk in enumerate(chunks, 1):
        log.info("  chunk %d/%d (%d chars)", i, len(chunks), len(chunk))
        data = _synth_chunk(chunk)
        seg = AudioSegment.from_file(io.BytesIO(data), format="mp3")
        # 段间 400ms 静音,听感更顺
        combined += seg + AudioSegment.silent(duration=400)
    combined.export(out_path, format="mp3", bitrate="96k")
    return out_path


def get_duration_seconds(mp3_path: Path) -> int:
    audio = AudioSegment.from_file(mp3_path)
    return int(round(len(audio) / 1000.0))
