"""Shared helpers for the talking-head-editor scripts. Standard library only."""
import glob
import json
import os
import re
import shutil
import subprocess

HOME = os.path.expanduser("~")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(HOME, ".cache", "talking-head-editor")

# Homebrew and user-level tools are not always on PATH in a non-login shell.
for extra in ("/opt/homebrew/bin", "/usr/local/bin", os.path.join(HOME, ".local", "bin")):
    if os.path.isdir(extra) and extra not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = extra + os.pathsep + os.environ.get("PATH", "")
# HyperFrames is tested on Node 22: when that line is installed, it goes first, ahead of
# any other `node` Homebrew may have linked into /opt/homebrew/bin.
_node22 = "/opt/homebrew/opt/node@22/bin"
if os.path.isdir(_node22):
    os.environ["PATH"] = _node22 + os.pathsep + os.environ.get("PATH", "")


def run(cmd, timeout=120, cwd=None, binary=False):
    """Run a command. Returns (returncode, stdout, stderr); never raises."""
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError:
        return 127, b"" if binary else "", "not found: %s" % cmd[0]
    except subprocess.TimeoutExpired:
        return 124, b"" if binary else "", "timed out after %ss: %s" % (timeout, " ".join(cmd[:3]))
    out = p.stdout if binary else p.stdout.decode("utf-8", "replace")
    return p.returncode, out, p.stderr.decode("utf-8", "replace")


def need(tool):
    if not shutil.which(tool):
        raise SystemExit(json.dumps({"error": "%s is not installed or not on PATH" % tool}))


def version_tuple(text):
    """'9.0.2_1' -> (9, 0, 2). None when there is no version in the text."""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))


def hyperframes_cmd():
    """The HyperFrames CLI: the plugin's pinned launcher when installed, else npx."""
    pattern = os.path.join(HOME, ".claude", "plugins", "cache", "hyperframes", "hyperframes",
                           "*", "skills", "hyperframes", "scripts", "plugin-cli.mjs")
    found = sorted(glob.glob(pattern), key=lambda p: version_tuple(p) or (0, 0, 0))
    if found:
        return ["node", found[-1]]
    return ["npx", "-y", "hyperframes"]


def probe(path):
    """ffprobe facts about a media file, as a plain dict."""
    need("ffprobe")
    code, out, err = run(["ffprobe", "-v", "error", "-print_format", "json",
                          "-show_format", "-show_streams", path])
    if code != 0:
        raise SystemExit(json.dumps({"error": "ffprobe failed", "detail": err.strip()[-400:]}))
    data = json.loads(out)
    v = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    a = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    info = {"file": path, "duration": float(data["format"].get("duration", 0) or 0),
            "bit_rate": int(data["format"].get("bit_rate", 0) or 0)}
    if v:
        def rate(r):
            n, _, d = (r or "0/1").partition("/")
            return float(n) / float(d or 1) if float(d or 1) else 0.0
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(sd["rotation"])
        rot = int(v.get("tags", {}).get("rotate", rot) or rot)
        fps, avg = rate(v.get("r_frame_rate")), rate(v.get("avg_frame_rate"))
        info.update({
            "width": v.get("width"), "height": v.get("height"),
            "fps": v.get("r_frame_rate"), "fps_float": round(fps, 3),
            "video_codec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"),
            "rotation": rot,
            "hdr": v.get("color_transfer") in ("smpte2084", "arib-std-b67"),
            "variable_frame_rate": bool(fps and avg and abs(fps - avg) / fps > 0.01),
        })
    if a:
        info.update({"audio_codec": a.get("codec_name"),
                     "audio_sample_rate": int(a.get("sample_rate", 0) or 0),
                     "audio_channels": a.get("channels")})
    else:
        info["audio_codec"] = None
    return info
