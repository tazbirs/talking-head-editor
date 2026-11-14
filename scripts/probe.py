#!/usr/bin/env python3
"""Report what an edit needs to know about a clip, as JSON.

usage: probe.py <video>
"""
import json
import sys

from common import probe, run


def keyframe_interval(path):
    """Largest gap between keyframes in the first 20 s, or None."""
    code, out, _ = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey",
                        "-show_entries", "frame=pts_time", "-of", "csv=p=0",
                        "-read_intervals", "%+20", path], timeout=180)
    times = []
    for line in out.splitlines():
        try:
            times.append(float(line.strip().strip(",")))
        except ValueError:
            pass
    if len(times) < 2:
        return None
    return round(max(b - a for a, b in zip(times, times[1:])), 3)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    info = probe(sys.argv[1])
    info["keyframe_interval_s"] = keyframe_interval(sys.argv[1])
    notes = []
    if info.get("hdr"):
        notes.append("HDR footage: convert to SDR (tonemap) before editing or it will look washed out.")
    if info.get("variable_frame_rate"):
        notes.append("Variable frame rate: re-encode to a constant rate before editing.")
    if (info.get("keyframe_interval_s") or 0) > 1:
        notes.append("Keyframes are more than 1 s apart: re-encode with -g <fps> or seeking will freeze.")
    if info.get("rotation"):
        notes.append("Rotation metadata present: bake the rotation in first.")
    if info.get("audio_codec") is None:
        notes.append("No audio track: there is no speech to time the edit to.")
    if (info.get("height") or 0) >= 2160 or (info.get("width") or 0) >= 3840:
        notes.append("4K source: scaffold with the matching 4K --resolution preset.")
    info["notes"] = notes
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
