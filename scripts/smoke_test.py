#!/usr/bin/env python3
"""Prove the toolchain still works: FFmpeg encode, Whisper timing, HyperFrames Bangla render.

usage: smoke_test.py [--keep]

Prints JSON with one entry per stage and the path of a rendered frame to look at.
Exit code 0 when every stage passed.
"""
import glob
import json
import os
import re
import shutil
import sys
import tempfile

from common import (CACHE_DIR, SKILL_DIR, SYSTEM, hyperframes_cmd, probe, run, run_whisper,
                    which, whisper_backend)

TITLE = "সম্পূর্ণ ফ্রি — ক্রেডিট ১০০০ · UNLIMITED"


SPEECH = "This is a quick test of the video editing tools."


def make_speech(work):
    """A short spoken clip from whatever speech synthesiser this system has, or None."""
    if SYSTEM == "Darwin" and which("say"):
        path = os.path.join(work, "voice.aiff")
        if run(["say", "-o", path, SPEECH])[0] == 0:
            return path
    for tool in ("espeak-ng", "espeak"):
        if which(tool):
            path = os.path.join(work, "voice.wav")
            if run([tool, "-w", path, SPEECH])[0] == 0:
                return path
    if SYSTEM == "Windows" and which("powershell"):
        path = os.path.join(work, "voice.wav")
        script = ("Add-Type -AssemblyName System.Speech; "
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "$s.SetOutputToWaveFile('%s'); $s.Speak('%s'); $s.Dispose()" % (path, SPEECH))
        if run(["powershell", "-NoProfile", "-Command", script], timeout=60)[0] == 0 and os.path.exists(path):
            return path
    return None


def stage_ffmpeg(work):
    clip = os.path.join(work, "clip.mp4")
    voice = make_speech(work)
    audio = ["-i", voice] if voice else ["-f", "lavfi", "-i", "sine=frequency=440:duration=3"]
    code, _, err = run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=navy:s=1280x720:r=30",
                        *audio, "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", clip],
                       timeout=120)
    if code != 0:
        return {"ok": False, "detail": err.strip()[-300:]}, None, False
    info = probe(clip)
    ok = info.get("video_codec") == "h264" and info.get("audio_codec") == "aac" and info["duration"] > 1
    return {"ok": ok, "detail": "h264 + aac, %.1fs" % info["duration"]}, clip, bool(voice)


def stage_whisper(work, clip, has_voice):
    engine = whisper_backend()
    if engine is None:
        return {"ok": False, "detail": "no Whisper is installed"}
    if not has_voice:
        return {"ok": True, "engine": engine,
                "skipped": "no speech synthesiser here to make test audio (Linux: install espeak-ng)"}
    wav = os.path.join(work, "speech-16k.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", clip, "-vn", "-ac", "1", "-ar", "16000", wav], timeout=60)
    path, error = run_whisper(wav, os.path.join(work, "whisper"), "t", model="tiny", language="en", timeout=900)
    if error:
        return {"ok": False, "engine": engine, "detail": error[-300:]}
    with open(path, encoding="utf-8") as f:
        words = [w for s in json.load(f).get("segments", []) for w in s.get("words", [])]
    return {"ok": len(words) >= 5, "engine": engine, "detail": "%d words with timestamps" % len(words)}


def stage_hyperframes(work):
    hf = hyperframes_cmd()
    code, out, err = run(hf + ["init", "smoke", "--example", "blank", "--non-interactive",
                               "--skip-skills", "--skip-transcribe"], timeout=300, cwd=work)
    proj = os.path.join(work, "smoke")
    index = os.path.join(proj, "index.html")
    if code != 0 or not os.path.exists(index):
        return {"ok": False, "detail": "init failed: " + (err or out).strip()[-300:]}
    os.makedirs(os.path.join(proj, "assets", "fonts"), exist_ok=True)
    shutil.copy(os.path.join(SKILL_DIR, "assets", "fonts", "HindSiliguri-Bold.ttf"),
                os.path.join(proj, "assets", "fonts"))
    with open(index, encoding="utf-8") as f:
        html = f.read()
    face = ('@font-face { font-family: "Hind Siliguri"; font-weight: 700; '
            'src: url("assets/fonts/HindSiliguri-Bold.ttf") format("truetype"); }\n')
    html = html.replace("<style>", "<style>\n" + face, 1)
    html = re.sub(r"--font-display:\s*[^;]+;", '--font-display: "Hind Siliguri", sans-serif;', html, 1)
    html = re.sub(r"font-weight:\s*600", "font-weight: 700", html, 1)
    html = html.replace('data-duration="10"', 'data-duration="2"')
    html = html.replace(">Title<", ">" + TITLE + "<")
    with open(index, "w", encoding="utf-8") as f:
        f.write(html)
    if TITLE not in html:
        return {"ok": False, "detail": "the blank template changed shape: update smoke_test.py"}

    code, out, err = run(hf + ["render"], timeout=900, cwd=proj)
    renders = sorted(glob.glob(os.path.join(proj, "renders", "*.mp4")), key=os.path.getmtime)
    if code != 0 or not renders:
        return {"ok": False, "detail": "render failed: " + (err or out).strip()[-300:]}
    os.makedirs(CACHE_DIR, exist_ok=True)
    frame = os.path.join(CACHE_DIR, "smoke-frame.png")
    run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", renders[-1], "-frames:v", "1",
         "-vf", "scale=960:-2", frame], timeout=60)
    # A drawn title has bright pixels on the dark ground; a blank frame has none.
    code, _, err = run(["ffmpeg", "-v", "info", "-i", frame, "-vf", "signalstats,metadata=print",
                        "-f", "null", "-"], timeout=60)
    ymax = re.search(r"YMAX=(\d+)", err)
    ymin = re.search(r"YMIN=(\d+)", err)
    drawn = bool(ymax and ymin and int(ymax.group(1)) - int(ymin.group(1)) > 60)
    info = probe(renders[-1])
    return {"ok": drawn, "frame": frame,
            "detail": "%sx%s, %.1fs, text %s. Look at the frame: only eyes can confirm the Bangla shaping."
                      % (info.get("width"), info.get("height"), info["duration"],
                         "drawn" if drawn else "NOT visible")}


def main():
    work = tempfile.mkdtemp(prefix="the-smoke-")
    result = {}
    try:
        result["ffmpeg"], clip, has_voice = stage_ffmpeg(work)
        result["whisper"] = stage_whisper(work, clip, has_voice) if clip else {"ok": False, "detail": "no test clip"}
        result["hyperframes"] = stage_hyperframes(work)
    finally:
        if "--keep" in sys.argv:
            result["work_dir"] = work
        else:
            shutil.rmtree(work, ignore_errors=True)
    result["ok"] = all(v.get("ok") for k, v in result.items() if isinstance(v, dict))
    result["frame"] = result.get("hyperframes", {}).get("frame")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
