#!/usr/bin/env python3
"""Check a rendered edit against its source, and lay out frames to look at.

usage: qc.py --source <raw video> --output <edited mp4> [--plan edit-plan.json] [--sheets <dir>]

Prints JSON: a list of checks (pass / warn / fail) and the contact sheets written.
The sheets are for looking at: this script cannot judge a frame, only produce it.
"""
import argparse
import array
import json
import os
import re
import shutil
import sys

from common import need, probe, run

ENV_RATE = 500      # envelope samples per second (2 ms resolution)
PCM_RATE = 8000
MAX_LAG_S = 0.5
WINDOW_S = 45


def envelope(path, start, seconds):
    code, raw, _ = run(["ffmpeg", "-v", "error", "-ss", "%.3f" % start, "-t", str(seconds), "-i", path,
                        # first_pts=0 pads from time zero, so an audio track that starts late
                        # is measured as late instead of being silently shifted back.
                        "-vn", "-af", "aresample=async=1:first_pts=0",
                        "-ac", "1", "-ar", str(PCM_RATE), "-f", "s16le", "-"],
                       timeout=300, binary=True)
    if code != 0 or len(raw) < PCM_RATE:
        return []
    pcm = array.array("h")
    pcm.frombytes(raw[: len(raw) // 2 * 2])
    block = PCM_RATE // ENV_RATE
    env = [sum(abs(s) for s in pcm[i:i + block]) / block for i in range(0, len(pcm) - block, block)]
    mean = sum(env) / len(env)
    return [e - mean for e in env]


def offset_ms(src_env, out_env):
    """How far the output's audio sits after the source's, in ms, and how sure we are (0-1)."""
    n = min(len(src_env), len(out_env))
    max_lag = int(MAX_LAG_S * ENV_RATE)
    if n < max_lag * 4:
        return None, 0.0
    a, b = src_env[:n], out_env[:n]
    norm = (sum(x * x for x in a) * sum(x * x for x in b)) ** 0.5
    if norm == 0:
        return None, 0.0
    best_lag, best = 0, -1.0
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            s = sum(x * y for x, y in zip(a[: n - lag], b[lag:]))
        else:
            s = sum(x * y for x, y in zip(a[-lag:], b[: n + lag]))
        if s > best:
            best, best_lag = s, lag
    return best_lag * 1000.0 / ENV_RATE, best / norm


def loudness(path):
    code, _, err = run(["ffmpeg", "-nostats", "-hide_banner", "-i", path, "-vn",
                        "-filter_complex", "ebur128=peak=true", "-f", "null", "-"], timeout=1800)
    tail = err[err.rfind("Summary:"):] if "Summary:" in err else ""
    i = re.search(r"I:\s*(-?[\d.]+) LUFS", tail)
    p = re.search(r"Peak:\s*(-?[\d.]+) dBFS", tail)
    return (float(i.group(1)) if i else None), (float(p.group(1)) if p else None)


def sheet_times(plan_path, duration):
    """(time, label) pairs worth looking at."""
    picks = []
    if plan_path and os.path.exists(plan_path):
        with open(plan_path, encoding="utf-8") as f:
            plan = json.load(f)
        for beat in plan.get("beats", []):
            treated = beat.get("graphic") or beat.get("layout", "full") != "full" or beat.get("camera")
            if not treated:
                continue
            start, end = float(beat["start"]), float(beat["end"])
            picks.append((min((start + end) / 2, duration - 0.05), beat.get("id", "")))
    if not picks:
        picks = [(duration * (i + 0.5) / 24, "t%d" % i) for i in range(24)]
    return picks


def contact_sheets(output, picks, out_dir):
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    frames_dir = os.path.join(out_dir, "frames")
    os.makedirs(frames_dir)
    sheets, per = [], 12
    for n in range(0, len(picks), per):
        chunk = picks[n:n + per]
        for k, (t, _) in enumerate(chunk):
            run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % max(t, 0), "-i", output,
                 "-frames:v", "1", "-vf", "scale=640:-2", os.path.join(frames_dir, "f%03d.jpg" % k)],
                timeout=120)
        sheet = os.path.join(out_dir, "sheet-%02d.jpg" % (n // per + 1))
        code, _, err = run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i",
                            os.path.join(frames_dir, "f%03d.jpg"), "-frames:v", "1",
                            "-vf", "tile=4x3:padding=6:color=black", sheet], timeout=120)
        for name in os.listdir(frames_dir):
            os.remove(os.path.join(frames_dir, name))
        if code == 0:
            sheets.append({"file": sheet, "reading_order": "left to right, top to bottom",
                           "frames": [{"time": round(t, 2), "beat": label} for t, label in chunk]})
    os.rmdir(frames_dir)
    return sheets


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--plan")
    ap.add_argument("--sheets", help="folder for contact sheets (default: beside the output)")
    args = ap.parse_args()
    need("ffmpeg")

    if not os.path.exists(args.output) or os.path.getsize(args.output) == 0:
        raise SystemExit(json.dumps({"error": "the output file is missing or empty"}))
    src, out = probe(args.source), probe(args.output)
    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    same_size = (src.get("width"), src.get("height")) == (out.get("width"), out.get("height"))
    add("resolution", "pass" if same_size else "fail",
        "source %sx%s, output %sx%s" % (src.get("width"), src.get("height"), out.get("width"), out.get("height")))
    fps_ok = abs((src.get("fps_float") or 0) - (out.get("fps_float") or 0)) < 0.02
    add("frame rate", "pass" if fps_ok else "fail",
        "source %s, output %s" % (src.get("fps"), out.get("fps")))
    frame = 1.0 / (out.get("fps_float") or 30)
    drift = out["duration"] - src["duration"]
    add("duration", "pass" if abs(drift) <= max(0.1, 2 * frame) else "fail",
        "source %.2fs, output %.2fs (%+.2fs)" % (src["duration"], out["duration"], drift))
    add("video codec", "pass" if out.get("video_codec") == "h264" else "fail", str(out.get("video_codec")))
    add("audio codec", "pass" if out.get("audio_codec") == "aac" else "fail", str(out.get("audio_codec")))
    add("pixel format", "pass" if out.get("pix_fmt") == "yuv420p" else "warn",
        "%s (yuv420p plays everywhere)" % out.get("pix_fmt"))

    # Voice sync: near the start and near the end, to catch a constant offset and a drift.
    shortest = min(src["duration"], out["duration"])
    windows = [("start", 0.0)]
    if shortest > WINDOW_S * 2.5:
        windows.append(("end", shortest - WINDOW_S - 1))
    for label, at in windows:
        off, sure = offset_ms(envelope(args.source, at, WINDOW_S), envelope(args.output, at, WINDOW_S))
        if off is None or sure < 0.3:
            add("voice sync (%s)" % label, "warn",
                "could not be measured (confidence %.2f): music or effects may mask the voice here" % sure)
        else:
            add("voice sync (%s)" % label, "pass" if abs(off) <= 40 else "fail",
                "output voice is %+.0f ms relative to the source (confidence %.2f)" % (off, sure))

    lufs, peak = loudness(args.output)
    if lufs is None:
        add("loudness", "warn", "could not be measured")
    else:
        add("loudness", "pass" if -18.0 <= lufs <= -12.0 else "warn",
            "%.1f LUFS integrated (YouTube target is about -14)" % lufs)
    if peak is not None:
        add("true peak", "pass" if peak <= -1.0 else "fail", "%.1f dBFS (limit -1.0)" % peak)

    sheets_dir = args.sheets or os.path.join(os.path.dirname(os.path.abspath(args.output)), "qc-sheets")
    sheets = contact_sheets(args.output, sheet_times(args.plan, out["duration"]), sheets_dir)

    worst = "fail" if any(c["status"] == "fail" for c in checks) else (
        "warn" if any(c["status"] == "warn" for c in checks) else "pass")
    print(json.dumps({"result": worst, "checks": checks, "contact_sheets": sheets,
                      "next": "Open every contact sheet and look at each frame before delivering."},
                     ensure_ascii=False, indent=2))
    return 1 if worst == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
