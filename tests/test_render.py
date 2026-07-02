"""Tests for the render module — pure functions only (no subprocess)."""
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
