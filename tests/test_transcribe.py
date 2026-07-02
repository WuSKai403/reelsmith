"""Test transcription module."""
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
