"""B-roll module for detecting and selecting performance footage."""
import random
from pathlib import Path
import config
from transcribe import get_duration

BROLL_DIR = config.BROLL_DIR


def detect_broll() -> list[Path]:
    """Detect MP4 files in the B-roll directory.

    Returns:
        Sorted list of Path objects for MP4 files, or empty list if directory
        doesn't exist or is empty.
    """
    if not BROLL_DIR.exists():
        return []
    return sorted(BROLL_DIR.glob("*.mp4"))


def select_broll_clip(broll_paths: list[Path], duration_secs: float) -> tuple[Path, float]:
    """Select a random B-roll clip and compute a random start offset.

    Args:
        broll_paths: List of video file paths to choose from
        duration_secs: Duration of the desired clip in seconds

    Returns:
        Tuple of (video path, random start offset in seconds)
        The offset ensures the clip can fit within the video.
    """
    path = random.choice(broll_paths)
    total = get_duration(str(path))
    max_start = max(0.0, total - duration_secs)
    return path, random.uniform(0.0, max_start)
