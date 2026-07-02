from pathlib import Path


def seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds to SRT time format: HH:MM:SS,mmm"""
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
    """Generate SRT subtitle file from transcript segments.

    Filters segments within [start_time, end_time) and resets timestamps
    relative to start_time (so start_time becomes 0:00:00,000).

    Args:
        segments: List of dicts with keys "text", "start", "end" (all in seconds)
        start_time: Start of time window (seconds)
        end_time: End of time window (seconds)
        output_path: Path where SRT file will be written

    Returns:
        output_path
    """
    # Filter segments that overlap with [start_time, end_time)
    in_range = [s for s in segments if s["end"] > start_time and s["start"] < end_time]

    lines = []
    for i, seg in enumerate(in_range, 1):
        # Reset timestamps relative to start_time
        t_start = max(seg["start"] - start_time, 0.0)
        t_end = min(seg["end"] - start_time, end_time - start_time)
        lines += [str(i), f"{seconds_to_srt_time(t_start)} --> {seconds_to_srt_time(t_end)}", seg["text"], ""]

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
