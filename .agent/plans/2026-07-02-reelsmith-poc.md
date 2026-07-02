# Reelsmith POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that takes two interview MP4 files, transcribes them with mlx-whisper, uses Claude to identify 3-5 highlight segments, and produces 9:16 short-form videos with subtitles, title cards, background music, and optional B-roll warmup.

**Architecture:** Single-entry Python script (`clip.py`) orchestrates independent modules. Transcript and candidates are cached in `cache/` to avoid re-running expensive steps. Pipeline: transcribe → analyze → (user picks) → auto-edit → crop → subtitle → title card → B-roll → music.

**Tech Stack:** Python 3.12, mlx-whisper, anthropic SDK, auto-editor, ffmpeg, ImageMagick (magick CLI), python-dotenv, pytest, uv

## Global Constraints

- Output resolution: 1080×1920 (9:16), H.264, 30fps
- Claude model: `claude-opus-4-8` with `thinking: {"type": "adaptive"}`
- Subtitle style: white, 22pt, bottom-center
- Music volume: -20dB relative to speech; fade in 1s, fade out 2s
- B-roll warmup: 7 seconds, immediately after title card — only if `input/broll/` contains `.mp4` files
- Title card duration: 3 seconds, black background, white text
- Segment length: 60–120 seconds
- Cache: `cache/transcript.json` and `cache/candidates.json` skip re-runs on second pass
- All subprocess calls use `check=True`; never swallow CalledProcessError
- Font for ImageMagick: `Noto-Sans-CJK-TC-Bold` (installed via brew cask font-noto-sans-cjk-tc)
- **Known limitation:** SRT timestamps are derived from the original transcript; after auto-editor removes silences the subtitle sync may drift slightly. Acceptable for POC.

---

## File Structure

```
reelsmith/
├── clip.py              # Orchestrator: entry point
├── config.py            # Env loading + path constants
├── transcribe.py        # mlx-whisper + timestamp merge
├── srt.py               # transcript JSON → SRT file
├── analyze.py           # Claude API segment selection
├── titlecard.py         # ImageMagick title card → 3s video
├── broll.py             # B-roll detection + random clip selection
├── render.py            # Full ffmpeg pipeline per candidate
├── .env                 # (gitignored)
├── .env.example
├── requirements.txt
└── tests/
    ├── __init__.py
    ├── test_transcribe.py
    ├── test_srt.py
    ├── test_analyze.py
    ├── test_titlecard.py
    ├── test_broll.py
    ├── test_render.py
    └── test_clip.py
```

---

### Task 1: Project setup

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `config.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: `config.ANTHROPIC_API_KEY`, `config.INTERVIEWEE_NAME`, `config.INTERVIEWEE_TITLE`, `config.MUSIC_VOLUME_DB`, `config.INPUT_DIR`, `config.BROLL_DIR`, `config.OUTPUT_DIR`, `config.CACHE_DIR`, `config.MUSIC_DIR` — all `Path` objects except `ANTHROPIC_API_KEY` (str) and `MUSIC_VOLUME_DB` (int)

- [ ] **Step 1: Create requirements.txt**

```
mlx-whisper
anthropic
auto-editor
python-dotenv
pytest
```

- [ ] **Step 2: Install system deps and Python env**

```bash
brew install ffmpeg imagemagick
brew install --cask font-noto-sans-cjk-tc
cd /Users/skai.wu/side/reelsmith
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Expected: no errors; `which ffmpeg` and `which magick` both return paths

- [ ] **Step 3: Create .env.example**

```
ANTHROPIC_API_KEY=sk-ant-...
INTERVIEWEE_NAME=受訪者姓名
INTERVIEWEE_TITLE=街頭藝人
```

- [ ] **Step 4: Create config.py**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
INTERVIEWEE_NAME: str = os.getenv("INTERVIEWEE_NAME", "受訪者")
INTERVIEWEE_TITLE: str = os.getenv("INTERVIEWEE_TITLE", "")
MUSIC_VOLUME_DB: int = -20

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
BROLL_DIR = INPUT_DIR / "broll"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / "cache"
MUSIC_DIR = BASE_DIR / "music"
```

- [ ] **Step 5: Create tests/__init__.py**

Empty file.

- [ ] **Step 6: Commit**

```bash
git -C /Users/skai.wu/side/reelsmith add requirements.txt .env.example config.py tests/__init__.py
git -C /Users/skai.wu/side/reelsmith commit -m "chore: project setup — config, deps, test scaffold"
```

---

### Task 2: Transcription module

**Files:**
- Create: `transcribe.py`
- Create: `tests/test_transcribe.py`

**Interfaces:**
- Produces: `get_duration(video_path: str) -> float`
- Produces: `merge_transcripts(part1: list[dict], part2: list[dict], part1_duration: float) -> list[dict]`
  Each dict: `{"text": str, "start": float, "end": float}`
- Produces: `transcribe_videos(part1_path: str, part2_path: str) -> list[dict]`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_transcribe.py
from transcribe import merge_transcripts

def test_merge_offsets_part2_timestamps():
    part1 = [{"text": "hello", "start": 0.0, "end": 1.5}]
    part2 = [{"text": "world", "start": 0.0, "end": 2.0}]
    result = merge_transcripts(part1, part2, part1_duration=10.0)
    assert len(result) == 2
    assert result[0]["start"] == 0.0
    assert result[1]["start"] == 10.0
    assert result[1]["end"] == 12.0

def test_merge_with_empty_part2():
    part1 = [{"text": "only part", "start": 0.0, "end": 5.0}]
    result = merge_transcripts(part1, [], part1_duration=10.0)
    assert len(result) == 1
    assert result[0]["start"] == 0.0

def test_merge_preserves_text():
    part1 = [{"text": "A", "start": 0.0, "end": 1.0}]
    part2 = [{"text": "B", "start": 0.0, "end": 1.0}]
    result = merge_transcripts(part1, part2, part1_duration=5.0)
    assert result[0]["text"] == "A"
    assert result[1]["text"] == "B"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/skai.wu/side/reelsmith && pytest tests/test_transcribe.py -v
```
Expected: `ImportError: cannot import name 'merge_transcripts'`

- [ ] **Step 3: Implement transcribe.py**

```python
import json
import subprocess
import mlx_whisper

def get_duration(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_path],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(result.stdout)
    return float(info["streams"][0]["duration"])

def _transcribe_one(video_path: str) -> list[dict]:
    result = mlx_whisper.transcribe(
        video_path,
        path_or_hf_repo="mlx-community/whisper-large-v3-mlx",
        language="zh",
        word_timestamps=True,
    )
    return [
        {"text": seg["text"].strip(), "start": seg["start"], "end": seg["end"]}
        for seg in result["segments"]
    ]

def merge_transcripts(
    part1: list[dict], part2: list[dict], part1_duration: float
) -> list[dict]:
    offset_part2 = [
        {**seg, "start": seg["start"] + part1_duration, "end": seg["end"] + part1_duration}
        for seg in part2
    ]
    return part1 + offset_part2

def transcribe_videos(part1_path: str, part2_path: str) -> list[dict]:
    print("⏳ Transcribing part 1...")
    part1 = _transcribe_one(part1_path)
    duration = get_duration(part1_path)
    print("⏳ Transcribing part 2...")
    part2 = _transcribe_one(part2_path)
    return merge_transcripts(part1, part2, duration)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_transcribe.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git -C /Users/skai.wu/side/reelsmith add transcribe.py tests/test_transcribe.py
git -C /Users/skai.wu/side/reelsmith commit -m "feat: transcription module — mlx-whisper + timestamp merge"
```

---

### Task 3: SRT generation

**Files:**
- Create: `srt.py`
- Create: `tests/test_srt.py`

**Interfaces:**
- Consumes: `list[dict]` from `merge_transcripts` — `{"text": str, "start": float, "end": float}`
- Produces: `seconds_to_srt_time(seconds: float) -> str` — e.g. `"00:01:30,123"`
- Produces: `generate_srt(segments: list[dict], start_time: float, end_time: float, output_path: Path) -> Path`
  Writes SRT with timestamps reset to 0 relative to `start_time`; returns `output_path`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_srt.py
import tempfile
from pathlib import Path
from srt import seconds_to_srt_time, generate_srt

def test_seconds_to_srt_time_zero():
    assert seconds_to_srt_time(0.0) == "00:00:00,000"

def test_seconds_to_srt_time_compound():
    assert seconds_to_srt_time(3661.5) == "01:01:01,500"

def test_seconds_to_srt_time_fractional():
    assert seconds_to_srt_time(90.123) == "00:01:30,123"

def test_generate_srt_filters_by_time_range():
    segments = [
        {"text": "before", "start": 0.0, "end": 5.0},
        {"text": "in range", "start": 10.0, "end": 15.0},
        {"text": "also in", "start": 20.0, "end": 25.0},
        {"text": "after", "start": 30.0, "end": 35.0},
    ]
    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as f:
        out = Path(f.name)
    generate_srt(segments, start_time=10.0, end_time=26.0, output_path=out)
    content = out.read_text()
    assert "in range" in content
    assert "also in" in content
    assert "before" not in content
    assert "after" not in content

def test_generate_srt_resets_timestamps():
    segments = [{"text": "hello", "start": 60.0, "end": 62.5}]
    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as f:
        out = Path(f.name)
    generate_srt(segments, start_time=60.0, end_time=70.0, output_path=out)
    content = out.read_text()
    assert "00:00:00,000" in content
    assert "00:00:02,500" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_srt.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement srt.py**

```python
from pathlib import Path

def seconds_to_srt_time(seconds: float) -> str:
    ms = round((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds) // 60 % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def generate_srt(
    segments: list[dict],
    start_time: float,
    end_time: float,
    output_path: Path,
) -> Path:
    in_range = [s for s in segments if s["end"] > start_time and s["start"] < end_time]
    lines = []
    for i, seg in enumerate(in_range, 1):
        t_start = max(seg["start"] - start_time, 0.0)
        t_end = min(seg["end"] - start_time, end_time - start_time)
        lines += [str(i), f"{seconds_to_srt_time(t_start)} --> {seconds_to_srt_time(t_end)}", seg["text"], ""]
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_srt.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git -C /Users/skai.wu/side/reelsmith add srt.py tests/test_srt.py
git -C /Users/skai.wu/side/reelsmith commit -m "feat: SRT generation from transcript segments"
```

---

### Task 4: Claude AI analysis

**Files:**
- Create: `analyze.py`
- Create: `tests/test_analyze.py`

**Interfaces:**
- Consumes: `list[dict]` transcript segments
- Produces: `build_transcript_text(segments: list[dict]) -> str`
- Produces: `parse_candidates(raw: str) -> list[dict]`
  Each dict: `{"id": int, "title": str, "angle": str, "start_time": float, "end_time": float, "hook": str, "summary": str, "broll_cues": list[float]}`
- Produces: `analyze_transcript(segments: list[dict]) -> list[dict]`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_analyze.py
from analyze import build_transcript_text, parse_candidates

def test_build_transcript_text_includes_timestamps():
    segments = [
        {"text": "Hello world", "start": 0.0, "end": 2.0},
        {"text": "Goodbye", "start": 63.0, "end": 65.0},
    ]
    text = build_transcript_text(segments)
    assert "[00:00]" in text
    assert "Hello world" in text
    assert "[01:03]" in text
    assert "Goodbye" in text

def test_parse_candidates_valid_json():
    raw = '{"candidates": [{"id": 1, "title": "Test", "angle": "A", "start_time": 10.0, "end_time": 80.0, "hook": "hook", "summary": "sum", "broll_cues": [20.0]}]}'
    result = parse_candidates(raw)
    assert len(result) == 1
    assert result[0]["title"] == "Test"
    assert result[0]["broll_cues"] == [20.0]

def test_parse_candidates_defaults_broll_cues_to_empty():
    raw = '{"candidates": [{"id": 1, "title": "T", "angle": "A", "start_time": 0.0, "end_time": 60.0, "hook": "h", "summary": "s"}]}'
    result = parse_candidates(raw)
    assert result[0]["broll_cues"] == []

def test_parse_candidates_strips_markdown_fences():
    raw = '```json\n{"candidates": [{"id": 1, "title": "T", "angle": "A", "start_time": 0.0, "end_time": 60.0, "hook": "h", "summary": "s", "broll_cues": []}]}\n```'
    result = parse_candidates(raw)
    assert result[0]["id"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_analyze.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement analyze.py**

```python
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
    lines = []
    for seg in segments:
        m = int(seg["start"]) // 60
        s = int(seg["start"]) % 60
        lines.append(f"[{m:02d}:{s:02d}] {seg['text']}")
    return "\n".join(lines)

def parse_candidates(raw: str) -> list[dict]:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    data = json.loads(match.group() if match else cleaned)
    for c in data["candidates"]:
        c.setdefault("broll_cues", [])
    return data["candidates"]

def analyze_transcript(segments: list[dict]) -> list[dict]:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_transcript_text(segments)}],
    )
    raw = next(b.text for b in response.content if b.type == "text")
    return parse_candidates(raw)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_analyze.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git -C /Users/skai.wu/side/reelsmith add analyze.py tests/test_analyze.py
git -C /Users/skai.wu/side/reelsmith commit -m "feat: Claude API segment analysis with adaptive thinking"
```

---

### Task 5: Title card (ImageMagick)

**Files:**
- Create: `titlecard.py`
- Create: `tests/test_titlecard.py`

**Interfaces:**
- Produces: `build_imagemagick_cmd(name: str, title: str, output_path: str) -> list[str]`
- Produces: `create_title_card(name: str, title: str, duration_secs: float, output_path: Path) -> Path`
  Generates a 1080×1920 PNG via ImageMagick, then converts to H.264 video; returns `output_path`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_titlecard.py
from titlecard import build_imagemagick_cmd

def test_cmd_starts_with_magick():
    cmd = build_imagemagick_cmd("林小明", "街頭音樂人", "/tmp/card.png")
    assert cmd[0] == "magick"

def test_cmd_contains_resolution():
    cmd = build_imagemagick_cmd("林小明", "街頭音樂人", "/tmp/card.png")
    assert "1080x1920" in " ".join(cmd)

def test_cmd_contains_name_and_title():
    cmd_str = " ".join(build_imagemagick_cmd("林小明", "街頭音樂人", "/tmp/card.png"))
    assert "林小明" in cmd_str
    assert "街頭音樂人" in cmd_str

def test_cmd_uses_black_background():
    cmd_str = " ".join(build_imagemagick_cmd("A", "B", "/tmp/out.png"))
    assert "xc:black" in cmd_str
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_titlecard.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement titlecard.py**

```python
import subprocess
from pathlib import Path

def build_imagemagick_cmd(name: str, title: str, output_path: str) -> list[str]:
    return [
        "magick",
        "-size", "1080x1920",
        "xc:black",
        "-font", "Noto-Sans-CJK-TC-Bold",
        "-pointsize", "72",
        "-fill", "white",
        "-gravity", "Center",
        "-annotate", "+0-80", name,
        "-pointsize", "48",
        "-fill", "#cccccc",
        "-annotate", "+0+20", title,
        str(output_path),
    ]

def create_title_card(name: str, title: str, duration_secs: float, output_path: Path) -> Path:
    img_path = output_path.parent / "_title_card.png"
    subprocess.run(build_imagemagick_cmd(name, title, str(img_path)), check=True)
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(img_path),
        "-c:v", "libx264", "-t", str(duration_secs),
        "-pix_fmt", "yuv420p", "-r", "30",
        "-an",
        str(output_path),
    ], check=True)
    return output_path
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_titlecard.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git -C /Users/skai.wu/side/reelsmith add titlecard.py tests/test_titlecard.py
git -C /Users/skai.wu/side/reelsmith commit -m "feat: ImageMagick title card → 3s H.264 video"
```

---

### Task 6: B-roll module

**Files:**
- Create: `broll.py`
- Create: `tests/test_broll.py`

**Interfaces:**
- Consumes: `config.BROLL_DIR` (Path), `get_duration` from `transcribe`
- Produces: `detect_broll() -> list[Path]` — MP4 files in `BROLL_DIR`, empty list if dir missing or empty
- Produces: `select_broll_clip(broll_paths: list[Path], duration_secs: float) -> tuple[Path, float]` — (video path, random start offset)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_broll.py
from pathlib import Path
from unittest.mock import patch
from broll import detect_broll, select_broll_clip

def test_detect_broll_missing_dir():
    with patch("broll.BROLL_DIR", Path("/nonexistent/xyz")):
        assert detect_broll() == []

def test_detect_broll_returns_only_mp4(tmp_path):
    (tmp_path / "a.mp4").touch()
    (tmp_path / "b.mp4").touch()
    (tmp_path / "notes.txt").touch()
    with patch("broll.BROLL_DIR", tmp_path):
        result = detect_broll()
    assert len(result) == 2
    assert all(p.suffix == ".mp4" for p in result)

def test_select_broll_clip_offset_within_bounds(tmp_path):
    p = tmp_path / "perf.mp4"
    p.touch()
    with patch("broll.get_duration", return_value=30.0):
        path, offset = select_broll_clip([p], duration_secs=7.0)
    assert path == p
    assert 0.0 <= offset <= 23.0  # 30.0 - 7.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_broll.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement broll.py**

```python
import random
from pathlib import Path
import config
from transcribe import get_duration

BROLL_DIR = config.BROLL_DIR

def detect_broll() -> list[Path]:
    if not BROLL_DIR.exists():
        return []
    return sorted(BROLL_DIR.glob("*.mp4"))

def select_broll_clip(broll_paths: list[Path], duration_secs: float) -> tuple[Path, float]:
    path = random.choice(broll_paths)
    total = get_duration(str(path))
    max_start = max(0.0, total - duration_secs)
    return path, random.uniform(0.0, max_start)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_broll.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git -C /Users/skai.wu/side/reelsmith add broll.py tests/test_broll.py
git -C /Users/skai.wu/side/reelsmith commit -m "feat: B-roll detection and random clip selection"
```

---

### Task 7: ffmpeg render pipeline

**Files:**
- Create: `render.py`
- Create: `tests/test_render.py`

**Interfaces:**
- Consumes: candidate dict, segments, config values, broll paths
- Produces: `build_crop_filter(width: int, height: int) -> str`
- Produces: `determine_source_file(start_time: float, part1_duration: float, part1: Path, part2: Path) -> tuple[Path, float]`
- Produces: `render_clip(candidate, segments, name, interviewee_title, output_dir, broll_paths, part1, part2, part1_duration) -> Path`

**Note:** `determine_source_file` assumes candidates don't span across both part files. Claude picks contained segments, so this holds in practice.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_render.py
from pathlib import Path
from render import build_crop_filter, determine_source_file

def test_build_crop_filter_4k():
    assert build_crop_filter(3840, 2160) == "crop=1215:2160:1312:0,scale=1080:1920"

def test_build_crop_filter_1080p():
    # 1920×1080 → crop_w = 1080*9/16 = 607, x = (1920-607)//2 = 656
    assert build_crop_filter(1920, 1080) == "crop=607:1080:656:0,scale=1080:1920"

def test_determine_source_in_part1():
    p1, p2 = Path("/i/p1.mp4"), Path("/i/p2.mp4")
    src, local = determine_source_file(30.0, 600.0, p1, p2)
    assert src == p1 and local == 30.0

def test_determine_source_in_part2():
    p1, p2 = Path("/i/p1.mp4"), Path("/i/p2.mp4")
    src, local = determine_source_file(700.0, 600.0, p1, p2)
    assert src == p2 and local == 100.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_render.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement render.py**

```python
import re
import random
import subprocess
from pathlib import Path

import config
from srt import generate_srt
from titlecard import create_title_card
from broll import select_broll_clip
from transcribe import get_duration

def build_crop_filter(width: int, height: int) -> str:
    crop_w = int(height * 9 / 16)
    x_offset = (width - crop_w) // 2
    return f"crop={crop_w}:{height}:{x_offset}:0,scale=1080:1920"

def determine_source_file(
    start_time: float, part1_duration: float, part1: Path, part2: Path
) -> tuple[Path, float]:
    if start_time < part1_duration:
        return part1, start_time
    return part2, start_time - part1_duration

def _extract_segment(source: Path, local_start: float, duration: float, output: Path) -> Path:
    subprocess.run([
        "ffmpeg", "-y", "-ss", str(local_start), "-i", str(source),
        "-t", str(duration), "-c", "copy", str(output),
    ], check=True)
    return output

def _auto_edit(input_path: Path, output_path: Path) -> Path:
    subprocess.run([
        "auto-editor", str(input_path), "--no-open", "-o", str(output_path),
    ], check=True)
    return output_path

def _crop_to_916(input_path: Path, output_path: Path) -> Path:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(input_path)],
        capture_output=True, text=True, check=True,
    )
    w, h = map(int, r.stdout.strip().split(","))
    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", build_crop_filter(w, h), "-c:a", "copy", str(output_path),
    ], check=True)
    return output_path

def _burn_subtitles(input_path: Path, srt_path: Path, output_path: Path) -> Path:
    style = "FontSize=22,PrimaryColour=&Hffffff,Alignment=2"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", f"subtitles={srt_path}:force_style='{style}'",
        "-c:a", "copy", str(output_path),
    ], check=True)
    return output_path

def _extract_broll_warmup(broll_paths: list[Path], output: Path) -> Path:
    src, offset = select_broll_clip(broll_paths, duration_secs=7.0)
    raw = output.parent / "_broll_raw.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-ss", str(offset), "-i", str(src),
        "-t", "7", "-c", "copy", str(raw),
    ], check=True)
    return _crop_to_916(raw, output)

def _concat_videos(parts: list[Path], output: Path) -> Path:
    concat_txt = output.parent / "_concat.txt"
    concat_txt.write_text("\n".join(f"file '{p}'" for p in parts))
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_txt), "-c", "copy", str(output),
    ], check=True)
    return output

def _mix_music(input_path: Path, output_path: Path) -> Path:
    music_files = list(config.MUSIC_DIR.glob("*.mp3"))
    if not music_files:
        subprocess.run(["ffmpeg", "-y", "-i", str(input_path), "-c", "copy", str(output_path)], check=True)
        return output_path
    music = random.choice(music_files)
    duration = get_duration(str(input_path))
    factor = 10 ** (config.MUSIC_VOLUME_DB / 20)
    fade_start = max(0.0, duration - 2)
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-stream_loop", "-1", "-i", str(music),
        "-filter_complex",
        f"[1:a]volume={factor:.4f},afade=t=in:d=1,afade=t=out:st={fade_start}:d=2[music];"
        f"[0:a][music]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(output_path),
    ], check=True)
    return output_path

def render_clip(
    candidate: dict,
    segments: list[dict],
    name: str,
    interviewee_title: str,
    output_dir: Path,
    broll_paths: list[Path],
    part1: Path,
    part2: Path,
    part1_duration: float,
) -> Path:
    work = output_dir / f"_work_{candidate['id']}"
    work.mkdir(parents=True, exist_ok=True)

    start, end = candidate["start_time"], candidate["end_time"]
    duration = end - start
    source, local_start = determine_source_file(start, part1_duration, part1, part2)

    raw = _extract_segment(source, local_start, duration, work / "raw.mp4")
    edited = _auto_edit(raw, work / "edited.mp4")
    cropped = _crop_to_916(edited, work / "cropped.mp4")

    srt_path = work / "clip.srt"
    generate_srt(segments, start, end, srt_path)
    subtitled = _burn_subtitles(cropped, srt_path, work / "subtitled.mp4")

    title_card = create_title_card(name, candidate["title"], 3.0, work / "title_card.mp4")

    parts = [title_card]
    if broll_paths:
        warmup = _extract_broll_warmup(broll_paths, work / "broll_warmup.mp4")
        parts.append(warmup)
    parts.append(subtitled)

    assembled = _concat_videos(parts, work / "assembled.mp4")

    safe_title = re.sub(r"[^\w一-鿿]", "_", candidate["title"])
    final = output_dir / f"clip_{candidate['id']:02d}_{safe_title}.mp4"
    _mix_music(assembled, final)
    return final
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_render.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git -C /Users/skai.wu/side/reelsmith add render.py tests/test_render.py
git -C /Users/skai.wu/side/reelsmith commit -m "feat: ffmpeg render pipeline — extract, crop, subtitle, title card, B-roll, music"
```

---

### Task 8: Main orchestrator

**Files:**
- Create: `clip.py`
- Create: `tests/test_clip.py`

**Interfaces:**
- Consumes: all modules above
- Produces: `parse_selection(raw: str, max_id: int) -> list[int]`
- Produces: `main()` — full CLI pipeline

- [ ] **Step 1: Write failing tests**

```python
# tests/test_clip.py
from clip import parse_selection

def test_parse_single():
    assert parse_selection("2", max_id=3) == [2]

def test_parse_multiple():
    assert parse_selection("1,3", max_id=3) == [1, 3]

def test_parse_all():
    assert parse_selection("all", max_id=3) == [1, 2, 3]

def test_parse_out_of_range_ignored():
    assert parse_selection("1,99", max_id=3) == [1]

def test_parse_invalid_token_ignored():
    assert parse_selection("1,abc,2", max_id=5) == [1, 2]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_clip.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement clip.py**

```python
import json
import sys
from pathlib import Path

import config
from transcribe import transcribe_videos, get_duration
from analyze import analyze_transcript
from broll import detect_broll
from render import render_clip

def parse_selection(raw: str, max_id: int) -> list[int]:
    if raw.strip().lower() == "all":
        return list(range(1, max_id + 1))
    result = []
    for token in raw.split(","):
        try:
            n = int(token.strip())
            if 1 <= n <= max_id:
                result.append(n)
        except ValueError:
            pass
    return result

def _print_candidates(candidates: list[dict]) -> None:
    print("\n" + "=" * 50)
    print("📋 候選短影音片段")
    print("=" * 50)
    for c in candidates:
        ms = int(c["start_time"]) // 60
        ss = int(c["start_time"]) % 60
        me = int(c["end_time"]) // 60
        se = int(c["end_time"]) % 60
        dur = int(c["end_time"] - c["start_time"])
        print(f"\n[{c['id']}] {c['title']}（{dur}秒，{ms:02d}:{ss:02d}–{me:02d}:{se:02d}）")
        print(f"    角度：{c['angle']}")
        print(f"    勾子：{c['hook']}")
        print(f"    摘要：{c['summary']}")
    print()

def main() -> None:
    part1 = config.INPUT_DIR / "part1.mp4"
    part2 = config.INPUT_DIR / "part2.mp4"
    transcript_cache = config.CACHE_DIR / "transcript.json"
    candidates_cache = config.CACHE_DIR / "candidates.json"
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    config.CACHE_DIR.mkdir(exist_ok=True)

    if transcript_cache.exists():
        print("✅ 使用快取逐字稿")
        segments = json.loads(transcript_cache.read_text())
    else:
        print("🎙️  開始轉逐字稿...")
        segments = transcribe_videos(str(part1), str(part2))
        transcript_cache.write_text(json.dumps(segments, ensure_ascii=False, indent=2))
        print(f"✅ 逐字稿完成，共 {len(segments)} 段")

    if candidates_cache.exists():
        print("✅ 使用快取候選段落")
        candidates = json.loads(candidates_cache.read_text())
    else:
        print("🤖 Claude 分析中...")
        candidates = analyze_transcript(segments)
        candidates_cache.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))

    _print_candidates(candidates)
    raw = input("輸入要產出的編號（逗號分隔，或輸入 all）：").strip()
    selected_ids = parse_selection(raw, max_id=len(candidates))
    if not selected_ids:
        print("❌ 沒有選擇任何片段，結束。")
        sys.exit(0)
    selected = [c for c in candidates if c["id"] in selected_ids]

    broll_paths = detect_broll()
    if broll_paths:
        print(f"🎬 找到 {len(broll_paths)} 支 B-roll 素材")
    else:
        print("⚠️  未找到 B-roll 素材，跳過")

    part1_duration = get_duration(str(part1))

    for candidate in selected:
        print(f"\n🎞️  產出「{candidate['title']}」...")
        path = render_clip(
            candidate=candidate,
            segments=segments,
            name=config.INTERVIEWEE_NAME,
            interviewee_title=config.INTERVIEWEE_TITLE,
            output_dir=config.OUTPUT_DIR,
            broll_paths=broll_paths,
            part1=part1,
            part2=part2,
            part1_duration=part1_duration,
        )
        print(f"✅  完成：{path}")

    print(f"\n🎉 全部完成！影片在 {config.OUTPUT_DIR}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/ -v
```
Expected: all tests PASS (24 total)

- [ ] **Step 5: Smoke test setup**

```bash
cp /Users/skai.wu/side/reelsmith/.env.example /Users/skai.wu/side/reelsmith/.env
# edit .env: fill in ANTHROPIC_API_KEY, INTERVIEWEE_NAME, INTERVIEWEE_TITLE
```

- [ ] **Step 6: Commit and push**

```bash
git -C /Users/skai.wu/side/reelsmith add clip.py tests/test_clip.py
git -C /Users/skai.wu/side/reelsmith commit -m "feat: main orchestrator — full pipeline with terminal UI and caching"
git -C /Users/skai.wu/side/reelsmith push origin main
```

---

## Verification Checklist (manual, run after placing real video files)

```bash
# Put interview files in place:
# cp your_interview_part1.mp4 input/part1.mp4
# cp your_interview_part2.mp4 input/part2.mp4
# cp performance.mp4 input/broll/perf_01.mp4  (optional)
# cp background_music.mp3 music/

python clip.py
```

- [ ] Executes without Python errors
- [ ] `cache/transcript.json` exists with correct timestamps (part2 times > part1 duration)
- [ ] Claude outputs valid JSON, 3-5 candidates printed to terminal
- [ ] Terminal selection input works
- [ ] Output video resolution: `ffprobe output/clip_01_*.mp4 | grep "1080x1920"`
- [ ] Title card visible for first 3 seconds
- [ ] Subtitles appear and roughly match speech
- [ ] Background music audibly quieter than speech
- [ ] With B-roll: performance clip appears after title card
- [ ] Without B-roll: flow completes without error
- [ ] Second run uses cached transcript and candidates (fast)
