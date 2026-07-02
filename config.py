import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
INTERVIEWEE_NAME: str = os.getenv("INTERVIEWEE_NAME", "受訪者")
INTERVIEWEE_TITLE: str = os.getenv("INTERVIEWEE_TITLE", "")
MUSIC_VOLUME_DB: int = -20

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
BROLL_DIR = INPUT_DIR / "broll"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / "cache"
MUSIC_DIR = BASE_DIR / "music"
