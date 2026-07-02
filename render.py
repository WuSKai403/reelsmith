"""ffmpeg render pipeline for producing 9:16 short-form interview clips."""
import json
import re
import random
import shutil
import subprocess
from pathlib import Path

import config
from srt import generate_srt
from titlecard import create_title_card
from broll import select_broll_clip
from transcribe import get_duration


def build_crop_filter(width: int, height: int) -> str:
    """Build an ffmpeg crop+scale filter string to produce a 9:16 vertical frame.

    Args:
        width: Source video width in pixels
        height: Source video height in pixels

    Returns:
        ffmpeg -vf filter string, e.g. "crop=1215:2160:1312:0,scale=1080:1920"
    """
    crop_w = int(height * 9 / 16)
    x_offset = (width - crop_w) // 2
    return f"crop={crop_w}:{height}:{x_offset}:0,scale=1080:1920"


def determine_source_file(
    start_time: float, part1_duration: float, part1: Path, part2: Path
) -> tuple[Path, float]:
    """Determine which source file a candidate segment comes from.

    Assumes the candidate is fully contained within one part (no cross-part spans).

    Args:
        start_time: Absolute start time of the candidate (seconds, merged timeline)
        part1_duration: Duration of part1 in seconds
        part1: Path to the first interview video file
        part2: Path to the second interview video file

    Returns:
        Tuple of (source Path, local start time within that file)
    """
    if start_time < part1_duration:
        source, local_start = part1, start_time
    else:
        source, local_start = part2, start_time - part1_duration
    return source, local_start


# ---------------------------------------------------------------------------
# Private pipeline helpers
# ---------------------------------------------------------------------------

def _extract_segment(source: Path, local_start: float, duration: float, output: Path) -> Path:
    """Extract a video segment using ffmpeg stream copy (fast, no re-encode)."""
    subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(local_start),
        "-i", str(source),
        "-t", str(duration),
        "-c", "copy",
        str(output),
    ], check=True)
    return output


def _auto_edit(input_path: Path, output_path: Path) -> Path:
    """Run auto-editor to remove silences / dead air from a clip."""
    subprocess.run([
        "auto-editor", str(input_path),
        "--no-open",
        "-o", str(output_path),
    ], check=True)
    return output_path


def _get_video_dimensions(video_path: Path) -> tuple[int, int]:
    """Return raw (width, height) of the first video stream via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    w, h = map(int, result.stdout.strip().split(","))
    return w, h


# Maps Display Matrix signed rotation → ffmpeg transpose filter to bake it in.
# auto-editor strips rotation metadata, so we detect from the original source
# and apply transpose during the crop step.
_TRANSPOSE_FILTER = {
    -90: "transpose=2",    # iPhone portrait (most common)
    90:  "transpose=1",
    180: "hflip,vflip",
    -180: "hflip,vflip",
}


def _detect_rotation(video_path: Path) -> int:
    """Return signed rotation in degrees from Display Matrix (0 if none)."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=side_data_list",
            "-of", "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        for sd in stream.get("side_data_list", []):
            if "rotation" in sd:
                return int(float(sd["rotation"]))
    return 0


def _crop_to_916(input_path: Path, output_path: Path, rotation: int = 0) -> Path:
    """Crop and scale a video to 1080×1920 (9:16) using centre crop.

    rotation: signed degrees from original source Display Matrix.
    Applies transpose to bake orientation before cropping.
    """
    w, h = _get_video_dimensions(input_path)
    filters = []
    transpose = _TRANSPOSE_FILTER.get(rotation)
    if transpose:
        filters.append(transpose)
        if abs(rotation) == 90:
            w, h = h, w  # swap to display dimensions after transpose
    filters.append(build_crop_filter(w, h))
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", ",".join(filters),
        "-c:a", "copy",
        str(output_path),
    ], check=True)
    return output_path


def _burn_subtitles(input_path: Path, srt_path: Path, output_path: Path) -> Path:
    """Burn SRT subtitles into the video using the subtitles filter."""
    # PlayResX/Y tells libass the actual canvas size so subtitle positions are correct.
    style = "FontSize=22,PrimaryColour=&Hffffff,Alignment=2,PlayResX=1080,PlayResY=1920"
    safe_path = str(srt_path).replace("'", r"\'").replace(":", r"\:")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", f"subtitles='{safe_path}':force_style='{style}'",
        "-c:a", "copy",
        str(output_path),
    ], check=True)
    return output_path


_BROLL_WARMUP_SECS = 7.0


def _extract_broll_warmup(broll_paths: list[Path], output: Path) -> Path:
    """Pick a random B-roll clip, extract warmup duration, then crop to 9:16."""
    src, offset = select_broll_clip(broll_paths, duration_secs=_BROLL_WARMUP_SECS)
    raw = output.parent / "_broll_raw.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(offset),
        "-i", str(src),
        "-t", str(_BROLL_WARMUP_SECS),
        "-c", "copy",
        str(raw),
    ], check=True)
    return _crop_to_916(raw, output)


def _concat_videos(parts: list[Path], output: Path) -> Path:
    """Concatenate video files using the ffmpeg concat demuxer."""
    concat_txt = output.parent / "_concat.txt"
    concat_txt.write_text("\n".join(f"file '{p}'" for p in parts))
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_txt),
        "-c", "copy",
        str(output),
    ], check=True)
    return output


def _mix_music(input_path: Path, output_path: Path) -> Path:
    """Mix background music into the video at MUSIC_VOLUME_DB.

    If no .mp3 files are found in MUSIC_DIR, copies input to output unchanged.
    """
    music_files = list(config.MUSIC_DIR.glob("*.mp3"))
    if not music_files:
        shutil.copy2(input_path, output_path)
        return output_path

    music = random.choice(music_files)
    vol_db = config.MUSIC_VOLUME_DB  # e.g. -20
    duration = get_duration(str(input_path))
    fade_out_start = max(0.0, duration - 2.0)
    filter_complex = (
        f"[1:a]volume={vol_db}dB,"
        f"afade=t=in:st=0:d=1,"
        f"afade=t=out:st={fade_out_start:.3f}:d=2[bg];"
        f"[0:a][bg]amix=inputs=2:duration=first[aout]"
    )
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-stream_loop", "-1",
        "-i", str(music),
        "-filter_complex",
        filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-shortest",
        str(output_path),
    ], check=True)
    return output_path


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

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
    """Render a single candidate segment into a 9:16 short-form clip.

    Pipeline:
        1. Extract raw segment from source file
        2. Run auto-editor to tighten pacing
        3. Crop to 9:16
        4. Burn subtitles
        5. Prepend title card (always first)
        6. (Optional) B-roll warmup after title card
        7. Concatenate all parts
        8. Mix in background music

    Args:
        candidate: Dict with keys: title, start_time, end_time, broll_cues
        segments: Full merged transcript segment list
        name: Interviewee display name
        interviewee_title: Interviewee title/role for title card
        output_dir: Directory to write the final clip
        broll_paths: List of B-roll video paths (may be empty)
        part1: Path to interview part 1
        part2: Path to interview part 2
        part1_duration: Duration of part1 in seconds (merged timeline offset)

    Returns:
        Path to the final rendered output file
    """
    start = candidate["start_time"]
    end = candidate["end_time"]
    duration = end - start

    # Guard: reject segments that cross the part1/part2 boundary
    if start < part1_duration < end:
        raise ValueError(
            f"Candidate '{candidate['title']}' spans both parts "
            f"({start:.1f}–{end:.1f}s, part1 ends at {part1_duration:.1f}s). "
            "Please select a segment fully within one part."
        )

    # Working directory inside output_dir for intermediate files
    work_dir = output_dir / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Extract raw segment
    source, local_start = determine_source_file(start, part1_duration, part1, part2)
    source_rotation = _detect_rotation(source)  # read before auto-editor strips it
    raw_segment = work_dir / "_01_raw.mp4"
    _extract_segment(source, local_start, duration, raw_segment)

    # Step 2: Auto-edit (silence removal) — strips rotation metadata
    auto_edited = work_dir / "_02_auto.mp4"
    _auto_edit(raw_segment, auto_edited)

    # Step 3: Crop to 9:16, baking in source rotation via transpose
    cropped = work_dir / "_03_cropped.mp4"
    _crop_to_916(auto_edited, cropped, rotation=source_rotation)

    # Step 4: Generate SRT and burn subtitles
    srt_path = work_dir / "_subtitles.srt"
    generate_srt(segments, start, end, srt_path)
    subbed = work_dir / "_04_subbed.mp4"
    _burn_subtitles(cropped, srt_path, subbed)

    # Step 5: Title card (3 seconds) — always first
    title_card = work_dir / "_05_titlecard.mp4"
    display_name = f"{name}  {interviewee_title}" if interviewee_title else name
    create_title_card(display_name, candidate["title"], 3.0, title_card)
    concat_parts: list[Path] = [title_card]

    # Step 6: Optional B-roll warmup after title card
    if broll_paths:
        broll_out = work_dir / "_06_broll.mp4"
        _extract_broll_warmup(broll_paths, broll_out)
        concat_parts.append(broll_out)

    # Interview clip last
    concat_parts.append(subbed)

    # Step 7: Concatenate
    concatenated = work_dir / "_07_concat.mp4"
    _concat_videos(concat_parts, concatenated)

    # Step 8: Mix music
    mixed = work_dir / "_08_mixed.mp4"
    _mix_music(concatenated, mixed)

    # Final output with safe filename
    safe_title = re.sub(r"[^\w一-鿿]", "_", candidate["title"])
    final_path = output_dir / f"{safe_title}.mp4"
    shutil.copy2(mixed, final_path)

    return final_path
