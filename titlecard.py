"""Title card generation using ImageMagick and ffmpeg."""
import subprocess
from pathlib import Path


def build_imagemagick_cmd(name: str, title: str, output_path: str) -> list[str]:
    """Build ImageMagick command for title card PNG generation.

    Args:
        name: Name of the interviewee
        title: Title/role of the interviewee
        output_path: Path to save the PNG

    Returns:
        Command list for subprocess.run()
    """
    return [
        "magick",
        "-size", "1080x1920",
        "xc:black",
        "-font", "Noto-Sans-CJK-TC-Bold",
        "-pointsize", "72",
        "-fill", "white",
        "-gravity", "Center",
        "-annotate", "+0-80", name,
        "-pointsize", "48",
        "-fill", "#cccccc",
        "-annotate", "+0+20", title,
        str(output_path),
    ]


def create_title_card(name: str, title: str, duration_secs: float, output_path: Path) -> Path:
    """Generate a title card video from PNG template.

    Args:
        name: Name of the interviewee
        title: Title/role of the interviewee
        duration_secs: Duration of the video in seconds
        output_path: Path to save the H.264 video

    Returns:
        Path to the generated video
    """
    img_path = output_path.parent / "_title_card.png"
    subprocess.run(build_imagemagick_cmd(name, title, str(img_path)), check=True)
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(img_path),
        "-c:v", "libx264", "-t", str(duration_secs),
        "-pix_fmt", "yuv420p", "-r", "30",
        "-an",
        str(output_path),
    ], check=True)
    return output_path
