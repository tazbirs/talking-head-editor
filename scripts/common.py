"""Shared helpers for the talking-head-editor scripts. Standard library only.

Runs on macOS (Apple Silicon and Intel), Linux and Windows.
"""
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(HOME, ".cache", "talking-head-editor")
SYSTEM = platform.system()                      # "Darwin", "Linux" or "Windows"
APPLE_SILICON = SYSTEM == "Darwin" and platform.machine() == "arm64"

# Bengali text must survive a Windows console, whose default encoding cannot hold it.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _prepend(path):
    parts = os.environ.get("PATH", "").split(os.pathsep)
    if os.path.isdir(path) and path not in parts:
        os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")


# Package-manager and user-level tool folders are not always on PATH in a non-login shell.
for _p in ("/opt/homebrew/bin", "/usr/local/bin", "/home/linuxbrew/.linuxbrew/bin",
           os.path.join(HOME, ".local", "bin"), os.path.join(HOME, ".cargo", "bin")):
    _prepend(_p)
# HyperFrames is tested on Node 22: where Homebrew has that line, it goes first, ahead of
# any other `node` linked into the main bin folder.
for _p in ("/opt/homebrew/opt/node@22/bin", "/usr/local/opt/node@22/bin"):
    if os.path.isdir(_p):
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")
        break


def which(name):
    return shutil.which(name)


def run(cmd, timeout=120, cwd=None, binary=False):
    """Run a command. Returns (returncode, stdout, stderr); never raises.

    The program is resolved through PATH first, so `npx`, `npm`, `claude` and friends are
    found on Windows, where they are .cmd files.
    """
    empty = b"" if binary else ""
    resolved = which(cmd[0]) or cmd[0]
    try:
        p = subprocess.run([resolved] + list(cmd[1:]), capture_output=True, timeout=timeout, cwd=cwd)
    except (FileNotFoundError, PermissionError, OSError):
        return 127, empty, "not found: %s" % cmd[0]
    except subprocess.TimeoutExpired:
        return 124, empty, "timed out after %ss: %s" % (timeout, " ".join(cmd[:3]))
    out = p.stdout if binary else p.stdout.decode("utf-8", "replace")
    return p.returncode, out, p.stderr.decode("utf-8", "replace")


def need(tool):
    if not which(tool):
        raise SystemExit(json.dumps({"error": "%s is not installed or not on PATH" % tool}))


def version_tuple(text):
    """'9.0.2_1' or '7:5.1.6-0+deb12u1' -> (9, 0, 2) / (5, 1, 6). None when there is no version."""
    text = re.sub(r"^\s*\d+:", "", text or "")          # distro epoch such as "7:"
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text)
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


# ---- Whisper: one interface, two engines -----------------------------------------------------
# mlx-whisper is the fast path on Apple Silicon. Everywhere else (Intel Mac, Linux, Windows)
# whisper-ctranslate2 runs the same models on CPU or an NVIDIA GPU.

MLX_MODELS = {"tiny": "mlx-community/whisper-tiny", "small": "mlx-community/whisper-small-mlx",
              "medium": "mlx-community/whisper-medium-mlx", "large-v3": "mlx-community/whisper-large-v3-mlx"}
WHISPER_INSTALL = {
    "mlx": "uv tool install --python 3.12 mlx-whisper",
    "faster": "uv tool install --python 3.12 whisper-ctranslate2",
}


def whisper_backend():
    """'mlx', 'faster' or None. THE_WHISPER_BACKEND forces one (used by tests)."""
    forced = os.environ.get("THE_WHISPER_BACKEND")
    if forced in ("mlx", "faster"):
        return forced
    if APPLE_SILICON and which("mlx_whisper"):
        return "mlx"
    if which("whisper-ctranslate2"):
        return "faster"
    if which("mlx_whisper"):
        return "mlx"
    return None


def whisper_install_hint():
    return WHISPER_INSTALL["mlx" if APPLE_SILICON else "faster"]


def run_whisper(audio, out_dir, name, model="large-v3", language=None, terms=None, timeout=3600):
    """Transcribe with word timestamps. Returns (path to <name>.json, None) or (None, error)."""
    backend = whisper_backend()
    if backend is None:
        return None, "No Whisper is installed. Install one with: " + whisper_install_hint()
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, name + ".json")
    if backend == "mlx":
        cmd = ["mlx_whisper", audio, "--model", MLX_MODELS.get(model, model),
               "--word-timestamps", "True", "--output-format", "json", "--output-dir", out_dir,
               "--output-name", name, "--condition-on-previous-text", "False", "--verbose", "False"]
        if language:
            cmd += ["--language", language]
        if terms:
            cmd += ["--initial-prompt", terms[:200]]
        produced = target
    else:
        cmd = ["whisper-ctranslate2", audio, "--model", model, "--word_timestamps", "True",
               "--output_format", "json", "--output_dir", out_dir,
               "--condition_on_previous_text", "False", "--verbose", "False"]
        if language:
            cmd += ["--language", language]
        if terms:
            cmd += ["--initial_prompt", terms[:200]]
        # This CLI names its output after the input file.
        produced = os.path.join(out_dir, os.path.splitext(os.path.basename(audio))[0] + ".json")
    code, out, err = run(cmd, timeout=timeout)
    if code != 0 or not os.path.exists(produced):
        return None, "%s whisper failed: %s" % (backend, (err or out).strip()[-500:])
    if produced != target:
        os.replace(produced, target)
    return target, None


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
