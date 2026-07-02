"""Claude AI analysis module for extracting candidate video segments."""
import json
import re
import anthropic
import config

_PROMPT_TEMPLATE = """你是一位短影音剪輯師，擅長從採訪中找出最有感染力的片段。
分析以下逐字稿，找出 {count_hint} 個最適合剪成獨立短影音的段落。
每個段落應：
- 有清楚的主題（一個核心訊息）
- 長度 {min_secs}-{max_secs} 秒
- 開頭有「勾人」的第一句話
- 結尾有完整的收束感

只輸出 JSON，不要其他文字：
{{
  "candidates": [
    {{
      "id": 1,
      "title": "段落標題",
      "angle": "這支影片的核心角度",
      "start_time": 83.2,
      "end_time": 145.8,
      "hook": "片段第一句話（吸引觀眾的句子）",
      "summary": "兩句話說明這段在講什麼",
      "broll_cues": [95.0, 120.5]
    }}
  ]
}}

broll_cues 是該片段內適合穿插 B-roll 的絕對時間點（秒）。無合適時機則給空陣列。"""


def _segment_params(total_secs: float) -> tuple[int, int, str]:
    """Return (min_secs, max_secs, count_hint) scaled to total video duration."""
    if total_secs >= 120:
        return 60, 120, "3-5"
    if total_secs >= 30:
        min_s = max(10, int(total_secs * 0.2))
        max_s = int(total_secs * 0.6)
        return min_s, max_s, "2-3"
    min_s = max(3, int(total_secs * 0.5))
    max_s = int(total_secs)
    return min_s, max_s, "1-2"


def build_transcript_text(segments: list[dict]) -> str:
    """Convert segment list to formatted transcript text with timestamps."""
    lines = []
    for seg in segments:
        m = int(seg["start"]) // 60
        s = int(seg["start"]) % 60
        lines.append(f"[{m:02d}:{s:02d}] {seg['text']}")
    return "\n".join(lines)


def parse_candidates(raw: str) -> list[dict]:
    """Parse Claude's response JSON, handling markdown code fences.

    Ensures broll_cues defaults to [] if absent.
    """
    # Remove markdown code fences (```json ... ``` or ``` ... ```)
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    # Extract JSON object from the cleaned string
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    data = json.loads(match.group() if match else cleaned)
    # Ensure broll_cues exists for each candidate
    for c in data["candidates"]:
        c.setdefault("broll_cues", [])
    return data["candidates"]


def analyze_transcript(segments: list[dict]) -> list[dict]:
    """Send transcript to Claude, parse and return candidate segments.

    Uses claude-opus-4-8 with adaptive thinking mode.
    Falls back to a single whole-clip candidate if total duration < 10s.
    """
    if not segments:
        return []

    total_secs = max(s["end"] for s in segments)

    # Fallback: video too short for meaningful analysis — return whole clip
    if total_secs < 10:
        print(f"⚠️  影片長度 {total_secs:.1f}s，直接使用整段作為候選片段")
        return [{
            "id": 1,
            "title": "完整片段",
            "angle": "完整採訪片段",
            "start_time": segments[0]["start"],
            "end_time": segments[-1]["end"],
            "hook": segments[0]["text"],
            "summary": "完整影片片段（自動 fallback）",
            "broll_cues": [],
        }]

    min_secs, max_secs, count_hint = _segment_params(total_secs)
    system_prompt = _PROMPT_TEMPLATE.format(
        min_secs=min_secs, max_secs=max_secs, count_hint=count_hint
    )

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=system_prompt,
        messages=[{"role": "user", "content": build_transcript_text(segments)}],
    )
    raw = next(b.text for b in response.content if b.type == "text")
    return parse_candidates(raw)
