"""Claude AI analysis module for extracting candidate video segments."""
import json
import re
import anthropic
import config

SYSTEM_PROMPT = """你是一位短影音剪輯師，擅長從採訪中找出最有感染力的片段。
分析以下逐字稿，找出 3-5 個最適合剪成獨立短影音的段落。
每個段落應：
- 有清楚的主題（一個核心訊息）
- 長度 60-120 秒
- 開頭有「勾人」的第一句話
- 結尾有完整的收束感

只輸出 JSON，不要其他文字：
{
  "candidates": [
    {
      "id": 1,
      "title": "段落標題",
      "angle": "這支影片的核心角度",
      "start_time": 83.2,
      "end_time": 145.8,
      "hook": "片段第一句話（吸引觀眾的句子）",
      "summary": "兩句話說明這段在講什麼",
      "broll_cues": [95.0, 120.5]
    }
  ]
}

broll_cues 是該片段內適合穿插 B-roll 的絕對時間點（秒）。無合適時機則給空陣列。"""


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
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_transcript_text(segments)}],
    )
    # Extract text content from response
    raw = next(b.text for b in response.content if b.type == "text")
    return parse_candidates(raw)
