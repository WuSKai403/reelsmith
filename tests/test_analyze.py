"""Tests for analyze module."""
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
