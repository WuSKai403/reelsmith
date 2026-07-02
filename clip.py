import json
import sys
from pathlib import Path

import config
from transcribe import transcribe_videos, get_duration
from analyze import analyze_transcript
from broll import detect_broll
from render import render_clip


def parse_selection(raw: str, max_id: int) -> list[int]:
    if raw.strip().lower() == "all":
        return list(range(1, max_id + 1))
    result = []
    for token in raw.split(","):
        try:
            n = int(token.strip())
            if 1 <= n <= max_id:
                result.append(n)
        except ValueError:
            pass
    return result


def _print_candidates(candidates: list[dict]) -> None:
    print("\n" + "=" * 50)
    print("📋 候選短影音片段")
    print("=" * 50)
    for c in candidates:
        ms = int(c["start_time"]) // 60
        ss = int(c["start_time"]) % 60
        me = int(c["end_time"]) // 60
        se = int(c["end_time"]) % 60
        dur = int(c["end_time"] - c["start_time"])
        print(f"\n[{c['id']}] {c['title']}（{dur}秒，{ms:02d}:{ss:02d}–{me:02d}:{se:02d}）")
        print(f"    角度：{c['angle']}")
        print(f"    勾子：{c['hook']}")
        print(f"    摘要：{c['summary']}")
    print()


def main() -> None:
    part1 = config.INPUT_DIR / "part1.mp4"
    part2 = config.INPUT_DIR / "part2.mp4"
    transcript_cache = config.CACHE_DIR / "transcript.json"
    candidates_cache = config.CACHE_DIR / "candidates.json"
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    config.CACHE_DIR.mkdir(exist_ok=True)

    # Step 1: Load or transcribe
    if transcript_cache.exists():
        print("✅ 使用快取逐字稿")
        segments = json.loads(transcript_cache.read_text())
    else:
        print("🎙️  開始轉逐字稿...")
        segments = transcribe_videos(str(part1), str(part2))
        transcript_cache.write_text(json.dumps(segments, ensure_ascii=False, indent=2))
        print(f"✅ 逐字稿完成，共 {len(segments)} 段")

    # Step 2: Load or analyze candidates
    if candidates_cache.exists():
        print("✅ 使用快取候選片段")
        candidates = json.loads(candidates_cache.read_text())
    else:
        print("🧠 分析逐字稿，尋找最佳片段...")
        candidates = analyze_transcript(segments)
        candidates_cache.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
        print(f"✅ 分析完成，找到 {len(candidates)} 個候選片段")

    # Step 3: Display candidates and get user selection
    _print_candidates(candidates)
    user_input = input("請選擇要剪輯的片段編號（例：1,2,3 或 all）：").strip()
    selected_ids = parse_selection(user_input, len(candidates))

    if not selected_ids:
        print("❌ 未選擇任何片段")
        sys.exit(1)

    print(f"✅ 已選擇 {len(selected_ids)} 個片段：{selected_ids}")

    # Step 4: Detect B-roll
    broll_paths = detect_broll()
    if broll_paths:
        print(f"✅ 發現 {len(broll_paths)} 個 B-roll 影片")
    else:
        print("⚠️  未發現 B-roll 影片（將跳過 B-roll 部分）")

    # Step 5: Get part1 duration for timeline offset
    part1_duration = get_duration(str(part1))
    print(f"✅ Part 1 時長：{part1_duration:.1f} 秒")

    # Step 6: Render selected clips
    print("\n🎬 開始渲染短影音...")
    rendered_clips = []
    for idx, candidate_id in enumerate(selected_ids, 1):
        candidate = candidates[candidate_id - 1]
        print(f"\n  [{idx}/{len(selected_ids)}] 正在渲染：{candidate['title']}")
        try:
            output_path = render_clip(
                candidate=candidate,
                segments=segments,
                name=config.INTERVIEWEE_NAME,
                interviewee_title=config.INTERVIEWEE_TITLE,
                output_dir=config.OUTPUT_DIR,
                broll_paths=broll_paths,
                part1=part1,
                part2=part2,
                part1_duration=part1_duration,
            )
            rendered_clips.append(output_path)
            print(f"  ✅ 完成：{output_path}")
        except Exception as e:
            print(f"  ❌ 失敗：{e}")

    # Step 7: Summary
    print("\n" + "=" * 50)
    print(f"✅ 渲染完成！共產出 {len(rendered_clips)} 個短影音：")
    for clip in rendered_clips:
        print(f"  - {clip}")
    print("=" * 50)


if __name__ == "__main__":
    main()
