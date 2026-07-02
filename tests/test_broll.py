"""Tests for the B-roll module."""
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
