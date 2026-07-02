# Reelsmith

採訪影片自動剪輯工具。輸入原始素材，AI 分析逐字稿選出精彩片段，產出 9:16 短影音。

設計文件：`~/side/docs/superpowers/specs/2026-07-02-interview-clip-poc-design.md`

---

## 技術棧

| 元件 | 工具 |
|------|------|
| 逐字稿 | mlx-whisper（M4 加速） |
| AI 選段 | Claude API claude-opus-4-8 |
| 微觀快剪 | Auto-Editor |
| 影片處理 | ffmpeg |
| 字卡 | ImageMagick + ffmpeg |
| 執行環境 | Python 3.12+，uv |

---

## 資料夾結構

```
input/
├── part1.mp4        ← 採訪第一支
├── part2.mp4        ← 採訪第二支
└── broll/           ← 表演/自有 B-roll（可選）
output/              ← 產出短影音
cache/               ← 逐字稿、候選段落快取
music/               ← 背景音樂（.mp3）
```

## 執行

```bash
python clip.py
```
