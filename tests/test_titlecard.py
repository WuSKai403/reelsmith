"""Test title card module."""
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
