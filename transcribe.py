"""Transcription module for interview video processing."""
import json
import subprocess
import mlx_whisper


def get_duration(video_path: str) -> float:
    """Get duration of video file in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "json",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def _transcribe_one(video_path: str) -> list[dict]:
    """Transcribe a single video file using mlx-whisper."""
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
    """Merge two transcripts, offsetting part2 timestamps by part1_duration."""
    offset_part2 = [
        {**seg, "start": seg["start"] + part1_duration, "end": seg["end"] + part1_duration}
        for seg in part2
    ]
    return part1 + offset_part2


def transcribe_videos(part1_path: str, part2_path: str | None = None) -> list[dict]:
    """Transcribe one or two interview video files and merge their transcripts."""
    print("⏳ Transcribing part 1...")
    part1 = _transcribe_one(part1_path)
    if part2_path is None:
        return part1
    duration = get_duration(part1_path)
    print("⏳ Transcribing part 2...")
    part2 = _transcribe_one(part2_path)
    return merge_transcripts(part1, part2, duration)
