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
