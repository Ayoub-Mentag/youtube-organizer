"""Phase 1: turn a Google Takeout Watch Later CSV into videos.json (id, title, channel).

Usage:
    python fetch.py "Watch later-videos.csv"

Needs the YOUTUBE_API_KEY environment variable (see .env.example).
Re-running is safe: videos already in videos.json are skipped.
"""
import csv
import json
import os
import sys
from pathlib import Path

from googleapiclient.discovery import build

OUT = Path("videos.json")


def read_ids(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    # First row is a header ("Video ID,Playlist Video Creation Timestamp")
    ids = [r[0].strip() for r in rows[1:] if r and r[0].strip()]
    return list(dict.fromkeys(ids))  # dedupe, keep order


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        sys.exit("YOUTUBE_API_KEY is not set. Put it in the .env file.")

    videos = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = [i for i in read_ids(sys.argv[1]) if i not in videos]
    print(f"{len(videos)} already saved, {len(todo)} to fetch")
    if not todo:
        return

    yt = build("youtube", "v3", developerKey=api_key)
    for start in range(0, len(todo), 50):  # API max: 50 ids per call
        batch = todo[start:start + 50]
        resp = yt.videos().list(part="snippet", id=",".join(batch)).execute()
        found = {item["id"]: item["snippet"] for item in resp.get("items", [])}
        for vid in batch:
            s = found.get(vid)
            videos[vid] = (
                {"title": s["title"], "channel": s["channelTitle"]}
                if s else {"title": None, "channel": None, "unavailable": True}
            )
        OUT.write_text(json.dumps(videos, ensure_ascii=False, indent=2))
        print(f"  {min(start + 50, len(todo))}/{len(todo)}")

    missing = sum(1 for v in videos.values() if v.get("unavailable"))
    print(f"Done. {len(videos)} videos saved to {OUT} ({missing} unavailable/deleted)")


if __name__ == "__main__":
    main()
