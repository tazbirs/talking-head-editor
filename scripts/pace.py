#!/usr/bin/env python3
"""Timing for a video with no voice: how long each on-screen line needs to be read.

usage: pace.py <lines file> --out <dir> [--base 0.5] [--per-word 0.3] [--gap 0.5] [--start 0]

The lines file has one on-screen line per line and a blank line between scenes. Text in
brackets is a note and is skipped. Each line is held for base + per-word x words seconds
(HyperFrames' reading pace); Bengali lines get 10% longer, since conjuncts read slower.

Writes the same files as transcribe.py, so the rest of the workflow does not change:
  <dir>/words.json      [{id, text, start, end, how: "paced"}]
  <dir>/sentences.json  [{id, text, start, end, words, scene}]
and prints a JSON summary with each scene's start and end.
"""
import argparse
import json
import os
import re
import sys
import unicodedata

import common  # noqa: F401  (sets UTF-8 output)

BENGALI = re.compile(r"[ঀ-৿]")
NOTE = re.compile(r"[\[(（].*?[\])）]")


def read_scenes(path):
    with open(path, encoding="utf-8") as f:
        text = unicodedata.normalize("NFC", f.read())
    scenes, current = [], []
    for raw in text.splitlines():
        line = NOTE.sub(" ", raw).strip()
        if not line:
            if current:
                scenes.append(current)
                current = []
            continue
        current.append(" ".join(line.split()))
    if current:
        scenes.append(current)
    return scenes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lines")
    ap.add_argument("--out", required=True)
    ap.add_argument("--base", type=float, default=0.5, help="seconds every line gets")
    ap.add_argument("--per-word", type=float, default=0.3, help="extra seconds per word")
    ap.add_argument("--gap", type=float, default=0.5, help="seconds between scenes, for the transition")
    ap.add_argument("--start", type=float, default=0.0,
                    help="seconds before the first line; keep 0, the first frame is the thumbnail")
    args = ap.parse_args()

    scenes = read_scenes(args.lines)
    if not scenes:
        raise SystemExit(json.dumps({"error": "the lines file has no on-screen lines"}))

    words, sentences, scene_times, t = [], [], [], args.start
    for s_idx, lines in enumerate(scenes):
        scene_start = t
        for line in lines:
            tokens = line.split()
            hold = args.base + args.per_word * len(tokens)
            if BENGALI.search(line):
                hold *= 1.1
            step = hold / len(tokens)
            first = len(words)
            for k, tok in enumerate(tokens):
                words.append({"id": "w%d" % len(words), "text": tok,
                              "start": round(t + k * step, 3), "end": round(t + (k + 1) * step, 3),
                              "how": "paced"})
            sentences.append({"id": "s%d" % len(sentences), "text": line, "start": round(t, 3),
                              "end": round(t + hold, 3),
                              "words": [words[first]["id"], words[-1]["id"]], "scene": s_idx})
            t += hold
        scene_times.append({"scene": s_idx, "start": round(scene_start, 3), "end": round(t, 3),
                            "lines": len(lines)})
        t += args.gap
    total = round(t - args.gap + 1.0, 3)        # one second on the last frame before the end

    os.makedirs(args.out, exist_ok=True)
    for name, data in (("words.json", words), ("sentences.json", sentences)):
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    long_lines = [s["text"] for s in sentences if len(s["text"].split()) > 10]
    summary = {"scenes": scene_times, "lines": len(sentences), "duration": total,
               "out": os.path.abspath(args.out)}
    if long_lines:
        summary["warning"] = "%d line(s) over 10 words: split them, a screen line is read, not heard." % len(long_lines)
        summary["long_lines"] = long_lines[:5]
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
