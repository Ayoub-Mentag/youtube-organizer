"""Phase 2: sort videos.json into categories with a local LLM (Ollama).

Usage:
    python classify.py

Reads videos.json, writes categories.json ({video_id: category}).
Re-running is safe: videos already classified are skipped, so you can resume
after a crash. Delete categories.json to start over.
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import yaml
from ollama import Client

CONFIG = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())
MODEL = CONFIG["model"]
BATCH_SIZE = CONFIG.get("batch_size", 25)
CATEGORIES = CONFIG["categories"]

VIDEOS = Path("videos.json")
OUT = Path("categories.json")


def pull_model(client):
    print(f"Checking model {MODEL} (first run downloads it, this can take a few minutes)...")
    last = -1
    for p in client.pull(MODEL, stream=True):
        total, done = getattr(p, "total", None), getattr(p, "completed", None)
        if total and done is not None:
            pct = int(done * 100 / total) // 10 * 10
            if pct != last:
                last = pct
                print(f"  downloading {pct}%")
    print("Model ready.")


def build_system_prompt():
    lines = "\n".join(f"- {name}: {desc}" for name, desc in CATEGORIES.items())
    return (
        "You sort YouTube videos into categories for a software engineer in their twenties.\n"
        "Pick exactly one category per video, using only these categories:\n"
        f"{lines}\n\n"
        "Always choose the closest matching category, even if the fit is imperfect. "
        "Judge by the title and the channel name. "
        "Return JSON with one entry per video, using the video's number as id."
    )


def build_schema():
    # The enum forces the model to answer with one of YOUR categories, nothing else.
    return {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "category": {"type": "string", "enum": list(CATEGORIES)},
                    },
                    "required": ["id", "category"],
                },
            }
        },
        "required": ["results"],
    }


def classify_batch(client, system, schema, batch):
    # Short numbers (1, 2, 3...) instead of 11-character video IDs: models garble long IDs.
    listing = "\n".join(
        f"{i}. [{info['channel']}] {info['title']}" for i, (_, info) in enumerate(batch, 1)
    )
    resp = client.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": listing},
        ],
        format=schema,
        options={"temperature": 0},
    )
    data = json.loads(resp.message.content)
    out = {}
    for item in data.get("results", []):
        idx, cat = item.get("id"), item.get("category")
        if isinstance(idx, int) and 1 <= idx <= len(batch) and cat in CATEGORIES:
            out[batch[idx - 1][0]] = cat
    return out


def main():
    if not VIDEOS.exists():
        sys.exit("videos.json not found. Run fetch.py first (Phase 1).")

    videos = json.loads(VIDEOS.read_text())
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    # Drop results whose category no longer exists in config.yaml (e.g. a removed 'Other'),
    # so those videos get classified again.
    done = {vid: cat for vid, cat in done.items() if cat in CATEGORIES}
    todo = [
        (vid, info) for vid, info in videos.items()
        if vid not in done and not info.get("unavailable")
    ]
    skipped = sum(1 for info in videos.values() if info.get("unavailable"))
    print(f"{len(done)} already classified, {len(todo)} to do, {skipped} unavailable (skipped)")

    if todo:
        client = Client(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
        pull_model(client)
        system, schema = build_system_prompt(), build_schema()

        for start in range(0, len(todo), BATCH_SIZE):
            batch = todo[start:start + BATCH_SIZE]
            print(
                f"  sorting videos {start + 1}-{start + len(batch)} of {len(todo)}... "
                "(the first batch is slower: it loads the model)",
                flush=True,
            )
            t0 = time.time()
            try:
                result = classify_batch(client, system, schema, batch)
            except Exception as e:  # keep going, the next run retries this batch
                print(f"  batch starting at {start} failed: {e}")
                continue
            done.update(result)
            OUT.write_text(json.dumps(done, ensure_ascii=False, indent=2))
            print(
                f"  done {min(start + BATCH_SIZE, len(todo))}/{len(todo)} "
                f"({len(result)}/{len(batch)} classified, {time.time() - t0:.0f}s)",
                flush=True,
            )

    print("\nResults:")
    for cat, n in Counter(done.values()).most_common():
        print(f"  {cat:<18} {n}")
    left = sum(1 for vid, _ in todo if vid not in done)
    if left:
        print(f"\n{left} videos were not classified. Run the same command again to retry them.")


if __name__ == "__main__":
    main()