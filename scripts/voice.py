#!/usr/bin/env python3
"""Make a voiceover from a narration file, and the timing that goes with it.

usage: voice.py <narration file> --out <dir> --engine say|kokoro|elevenlabs|azure|edge
                [--voice <name or id>] [--gender male|female] [--language bn|en]
                [--lines <on-screen lines file>] [--rate <engine rate>]
                [--lead 0.4] [--pause 0.4] [--gap 0.6] [--min 2.3]
       voice.py --list                        engines and built-in voices
       voice.py --list --engine elevenlabs    the voices and Bangla-capable models in the person's account

The narration file has one spoken passage per line and a blank line between scenes; text in
brackets is a note. Each passage is spoken separately, so its length is known exactly and
the video can be timed to it without transcription.

Writes <dir>/voiceover.wav    the whole narration, 48 kHz mono, about -16 LUFS
       <dir>/sentences.json   one entry per passage: start, end, scene (same shape as pace.py)
       <dir>/words.json       words spread evenly inside each passage
       <dir>/segments/        one cached file per passage (re-runs only re-speak changed text)
and prints a JSON summary.

With --lines (a file of on-screen lines matching the narration passage for passage),
sentences.json carries the on-screen text and keeps the spoken text under "spoken".

Engines
  say     macOS built-in voices. Local and free. Bangla: Piya (female) only. A draft voice.
  kokoro  HyperFrames' local Kokoro model. Local and free. Natural English; no Bangla.
  elevenlabs  ElevenLabs (official). The most expressive Bangla and English voices. Needs
          ELEVENLABS_API_KEY, and --voice with a voice name or id from the person's account. The
          model is picked from those the voice is verified on for the language (--model overrides).
          Library voices through the API, and publishing, need a paid plan.
  azure   Microsoft Azure Speech (official). Natural Bangla and English, male and female.
          Needs AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in the environment.
  edge    The same Microsoft neural voices through the unofficial `edge-tts` tool. No account,
          but it is not a licensed route: use only when the person has chosen it.
azure and edge send the narration text to Microsoft; elevenlabs sends it to ElevenLabs.

Keys are read from the environment, or from ~/.config/talking-head-editor/keys.env (NAME=value
lines, a file the person creates themselves). They are never printed or written anywhere.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
import wave
from xml.sax.saxutils import escape

from common import CACHE_DIR, SYSTEM, hyperframes_cmd, need, probe, run, which
from pace import read_scenes

RATE = 48000
BENGALI = re.compile(r"[ঀ-৿]")

# engine -> language -> gender -> voice
VOICES = {
    "say": {"bn": {"female": "Piya"}, "en": {"female": "Samantha", "male": "Daniel"}},
    "kokoro": {"en": {"female": "af_heart", "male": "am_adam"}},
    "azure": {"bn": {"male": "bn-BD-PradeepNeural", "female": "bn-BD-NabanitaNeural"},
              "en": {"male": "en-US-GuyNeural", "female": "en-US-JennyNeural"}},
}
VOICES["edge"] = VOICES["azure"]
VOICES["elevenlabs"] = {}      # voices live in the person's account: pass --voice
ELEVEN_API = "https://api.elevenlabs.io/v1"
KEYS_FILE = os.path.join(os.path.expanduser("~"), ".config", "talking-head-editor", "keys.env")
NOTES = {
    "say": "macOS only, local. Apple's licence covers personal, non-commercial use: a draft voice.",
    "kokoro": "Local, natural English. Installs on first use.",
    "elevenlabs": "Official. Needs ELEVENLABS_API_KEY and --voice; the model is chosen from what the voice is "
                  "verified on for the language. Library voices and publishing need a paid plan. "
                  "Sends text to ElevenLabs.",
    "azure": "Official and licensed. Needs AZURE_SPEECH_KEY and AZURE_SPEECH_REGION. Sends text to Microsoft.",
    "edge": "Unofficial access to Microsoft's voices: no account, not a licensed route. Sends text to Microsoft.",
}


def fail(message, **extra):
    raise SystemExit(json.dumps(dict({"error": message}, **extra), ensure_ascii=False))


def secret(name):
    """A key from the environment, else from the person's own keys file. Never logged."""
    value = os.environ.get(name)
    if value:
        return value.strip()
    try:
        with open(KEYS_FILE, encoding="utf-8") as f:
            for line in f:
                key, _, val = line.strip().partition("=")
                if key.strip() == name and val.strip():
                    return val.strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def eleven_get(path):
    """GET from the ElevenLabs API. Returns (data, None) or (None, error)."""
    key = secret("ELEVENLABS_API_KEY")
    if not key:
        return None, "ELEVENLABS_API_KEY is not set (environment, or %s)" % KEYS_FILE
    req = urllib.request.Request(ELEVEN_API + path, headers={"xi-api-key": key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        return None, "ElevenLabs refused the request: HTTP %s %s" % (e.code, e.reason)
    except Exception as e:
        return None, "ElevenLabs could not be reached: %s" % e


def eleven_overview(language="bn"):
    """The person's voices, and the models that can speak `language`."""
    voices, error = eleven_get("/voices")
    if error:
        return None, error
    models, error = eleven_get("/models")
    if error:
        return None, error
    able = [m["model_id"] for m in models if m.get("can_do_text_to_speech")
            and any(l.get("language_id") == language for l in m.get("languages", []))]
    listing = [{"name": v.get("name"), "voice_id": v.get("voice_id"), "category": v.get("category"),
                "gender": (v.get("labels") or {}).get("gender"), "accent": (v.get("labels") or {}).get("accent"),
                "language": (v.get("labels") or {}).get("language")} for v in voices.get("voices", [])]
    return {"models_for_%s" % language: able, "voices": listing}, None


def eleven_voice_id(asked):
    """Accept a voice id as it is, or find a voice by name in the person's account."""
    if re.fullmatch(r"[A-Za-z0-9]{20}", asked or ""):
        return asked, None
    voices, error = eleven_get("/voices")
    if error:
        return None, error
    names = {(v.get("name") or "").lower(): v.get("voice_id") for v in voices.get("voices", [])}
    wanted = (asked or "").lower()
    hits = [vid for name, vid in names.items() if name == wanted] or \
           [vid for name, vid in names.items() if name.startswith(wanted)]
    if len(hits) == 1:
        return hits[0], None
    return None, ("No single voice named %r in this ElevenLabs account. Add the voice to the account's "
                  "voices first; `voice.py --list --engine elevenlabs` shows what is there." % asked)


ELEVEN_PREFERENCE = ["eleven_v4", "eleven_v3", "eleven_multilingual_v2", "eleven_turbo_v2_5", "eleven_flash_v2_5"]


def eleven_model(voice_id, language, asked):
    """Which model to speak with. Returns (model id, whether the voice is verified in this language on it).

    A library voice is verified per language and per model, and the same voice can be a Hindi
    voice on one model and a Bangla voice on another. Use a model it is verified on for this language.
    """
    detail, _ = eleven_get("/voices/%s" % voice_id)
    verified = [v.get("model_id") for v in ((detail or {}).get("verified_languages") or [])
                if v.get("language") == language]
    if asked:
        return asked, asked in verified
    for model in ELEVEN_PREFERENCE:
        if model in verified:
            return model, True
    if verified:
        return verified[0], True
    return ("eleven_v3" if language == "bn" else "eleven_multilingual_v2"), False


def pick_voice(engine, language, gender, asked):
    if engine == "elevenlabs":
        if not asked:
            fail("ElevenLabs voices are chosen by the person: pass --voice with a voice name or id.",
                 fix="python3 voice.py --list --engine elevenlabs")
        voice_id, error = eleven_voice_id(asked)
        if error:
            fail(error)
        return voice_id
    if asked:
        return asked
    by_gender = VOICES.get(engine, {}).get(language)
    if not by_gender:
        fail("The %s engine has no %s voice." % (engine, "Bangla" if language == "bn" else language),
             fix="For Bangla use --engine azure (or edge, if the person chose it), or the person's own recording.")
    if gender not in by_gender:
        fail("The %s engine has no %s %s voice; it has: %s." % (engine, gender, language, ", ".join(by_gender)),
             fix="Pick another engine, or pass --gender %s." % next(iter(by_gender)))
    return by_gender[gender]


def ensure_kokoro():
    """HyperFrames' `tts` needs a Python that has kokoro-onnx. Give it one, made once with uv."""
    if os.environ.get("HYPERFRAMES_PYTHON"):
        return None
    venv = os.path.join(CACHE_DIR, "kokoro-venv")
    python = os.path.join(venv, "Scripts" if SYSTEM == "Windows" else "bin", "python.exe" if SYSTEM == "Windows" else "python")
    if not os.path.exists(python):
        if not which("uv"):
            return "the kokoro engine needs uv to set itself up (see references/platforms.md)"
        os.makedirs(CACHE_DIR, exist_ok=True)
        code, out, err = run(["uv", "venv", venv, "--python", "3.12"], timeout=600)
        if code == 0:
            code, out, err = run(["uv", "pip", "install", "--python", python, "kokoro-onnx", "soundfile"], timeout=1800)
        if code != 0:
            return "could not install the Kokoro voice: " + (err or out).strip()[-300:]
    os.environ["HYPERFRAMES_PYTHON"] = python
    return None


def speak(engine, voice, language, rate, text, raw, model=None):
    """Speak one passage into `raw` (any audio format). Returns an error string or None."""
    if engine == "say":
        if SYSTEM != "Darwin" or not which("say"):
            return "the say engine exists only on macOS"
        cmd = ["say", "-v", voice, "-o", raw] + (["-r", str(rate)] if rate else []) + [text]
        code, out, err = run(cmd, timeout=300)
        return None if code == 0 and os.path.exists(raw) else "say failed: " + (err or out).strip()[-200:]
    if engine == "kokoro":
        problem = ensure_kokoro()
        if problem:
            return problem
        cmd = hyperframes_cmd() + ["tts", text, "-v", voice, "-o", raw] + (["-s", str(rate)] if rate else [])
        code, out, err = run(cmd, timeout=900)
        return None if code == 0 and os.path.exists(raw) else "kokoro failed: " + (err or out).strip()[-300:]
    if engine == "edge":
        runner = ["uvx", "edge-tts"] if which("uvx") else ["edge-tts"]
        cmd = runner + ["--voice", voice, "--text", text, "--write-media", raw] + (["--rate", str(rate)] if rate else [])
        code, out, err = run(cmd, timeout=300)
        return None if code == 0 and os.path.exists(raw) else "edge-tts failed: " + (err or out).strip()[-300:]
    if engine == "elevenlabs":
        key = secret("ELEVENLABS_API_KEY")
        if not key:
            return "ELEVENLABS_API_KEY is not set (environment, or %s)" % KEYS_FILE
        body = {"text": text, "model_id": model or "eleven_v3", "language_code": language}
        if rate:
            body["voice_settings"] = {"speed": float(rate)}
        req = urllib.request.Request(
            "%s/text-to-speech/%s?output_format=mp3_44100_128" % (ELEVEN_API, voice),
            data=json.dumps(body).encode("utf-8"),
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r, open(raw, "wb") as f:
                f.write(r.read())
        except urllib.error.HTTPError as e:
            try:
                detail = json.load(e).get("detail")
                detail = detail.get("message") if isinstance(detail, dict) else detail
            except Exception:
                detail = None
            return "ElevenLabs refused the request: HTTP %s %s" % (e.code, str(detail or e.reason)[:300])
        except Exception as e:
            return "ElevenLabs could not be reached: %s" % e
        return None
    if engine == "azure":
        key, region = secret("AZURE_SPEECH_KEY"), secret("AZURE_SPEECH_REGION")
        if not key or not region:
            return "AZURE_SPEECH_KEY and AZURE_SPEECH_REGION are not set"
        locale = "-".join(voice.split("-")[:2])
        prosody = '<prosody rate="%s">%s</prosody>' % (rate, escape(text)) if rate else escape(text)
        ssml = ('<speak version="1.0" xml:lang="%s"><voice name="%s">%s</voice></speak>' % (locale, voice, prosody))
        req = urllib.request.Request(
            "https://%s.tts.speech.microsoft.com/cognitiveservices/v1" % region, data=ssml.encode("utf-8"),
            headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml",
                     "X-Microsoft-OutputFormat": "riff-48khz-16bit-mono-pcm", "User-Agent": "talking-head-editor"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r, open(raw, "wb") as f:
                f.write(r.read())
        except urllib.error.HTTPError as e:
            return "Azure Speech refused the request: HTTP %s %s" % (e.code, e.reason)
        except Exception as e:
            return "Azure Speech could not be reached: %s" % e
        return None
    return "unknown engine %s" % engine


def to_pcm(raw, wav):
    """Any audio -> 48 kHz mono 16-bit WAV, with the silence at both ends trimmed."""
    trim = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.03,areverse,"
            "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.08,areverse")
    code, _, err = run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af", trim, "-ac", "1", "-ar", str(RATE),
                        "-c:a", "pcm_s16le", wav], timeout=120)
    return None if code == 0 else err.strip()[-200:]


def read_pcm(path):
    with wave.open(path, "rb") as w:
        return w.readframes(w.getnframes())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("narration", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--engine", choices=sorted(NOTES))
    ap.add_argument("--voice")
    ap.add_argument("--model", help="elevenlabs only: model id. Default: a model the voice is verified on for the language")
    ap.add_argument("--gender", choices=["male", "female"], default="male")
    ap.add_argument("--language", help="bn or en; detected from the narration when omitted")
    ap.add_argument("--lines", help="on-screen lines file matching the narration passage for passage")
    ap.add_argument("--rate", help="speaking rate in the engine's own unit (say: words per minute; kokoro and "
                                   "elevenlabs: multiplier such as 0.95; azure and edge: e.g. +8%%)")
    ap.add_argument("--lead", type=float, default=0.4, help="silence before the first word, so the voice does not start on frame 0")
    ap.add_argument("--pause", type=float, default=0.4, help="silence after each passage")
    ap.add_argument("--gap", type=float, default=0.6, help="extra silence between scenes")
    ap.add_argument("--min", type=float, default=2.3, help="shortest time a passage holds the screen")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list and args.engine == "elevenlabs":
        overview, error = eleven_overview(args.language or "bn")
        if error:
            fail(error)
        print(json.dumps(overview, ensure_ascii=False, indent=2))
        return 0
    if args.list:
        print(json.dumps({"engines": NOTES, "voices": {k: v for k, v in VOICES.items()}}, ensure_ascii=False, indent=2))
        return 0
    if not (args.narration and args.out and args.engine):
        ap.error("narration file, --out and --engine are required")
    need("ffmpeg")

    scenes = read_scenes(args.narration)
    if not scenes:
        fail("the narration file has no spoken lines")
    flat = [(k, text) for k, scene in enumerate(scenes) for text in scene]
    language = args.language or ("bn" if BENGALI.search(" ".join(t for _, t in flat)) else "en")
    voice = pick_voice(args.engine, language, args.gender, args.voice)
    model, verified = None, None
    if args.engine == "elevenlabs":
        model, verified = eleven_model(voice, language, args.model or secret("ELEVENLABS_MODEL"))

    shown = None
    if args.lines:
        shown_scenes = read_scenes(args.lines)
        if [len(s) for s in shown_scenes] != [len(s) for s in scenes]:
            fail("The narration and the on-screen lines do not match passage for passage.",
                 narration=[len(s) for s in scenes], lines=[len(s) for s in shown_scenes])
        shown = [t for s in shown_scenes for t in s]

    seg_dir = os.path.join(args.out, "segments")
    os.makedirs(seg_dir, exist_ok=True)
    silence = lambda seconds: b"\x00\x00" * int(round(seconds * RATE))
    audio, sentences, words, spoken_seconds, made = bytearray(silence(args.lead)), [], [], 0.0, 0
    for i, (scene, text) in enumerate(flat):
        tag = hashlib.sha1(("%s|%s|%s|%s|%s" % (args.engine, voice, model, args.rate, text)).encode("utf-8")).hexdigest()[:16]
        wav = os.path.join(seg_dir, tag + ".wav")
        if not os.path.exists(wav):
            raw = os.path.join(seg_dir, tag + {"say": ".aiff", "edge": ".mp3", "elevenlabs": ".mp3"}.get(args.engine, ".wav").replace(".wav", ".src.wav"))
            error = speak(args.engine, voice, language, args.rate, text, raw, model) or to_pcm(raw, wav)
            if os.path.exists(raw):
                os.remove(raw)
            if error:
                fail("Passage %d could not be spoken: %s" % (i + 1, error), passage=text)
            made += 1
        pcm = read_pcm(wav)
        dur = len(pcm) / 2 / RATE
        if dur < 0.2:
            fail("Passage %d came out silent: the voice may not read this text." % (i + 1), passage=text)
        if i and flat[i - 1][0] != scene:
            audio += silence(args.gap)
        start = len(audio) / 2 / RATE
        audio += pcm
        hold = max(dur + args.pause, args.min)
        audio += silence(hold - dur)
        toks = text.split()
        first = len(words)
        for k, tok in enumerate(toks):
            words.append({"id": "w%d" % len(words), "text": tok, "start": round(start + dur * k / len(toks), 3),
                          "end": round(start + dur * (k + 1) / len(toks), 3), "how": "voice"})
        entry = {"id": "s%d" % i, "text": shown[i] if shown else text, "start": round(start, 3),
                 "end": round(start + hold, 3), "words": [words[first]["id"], words[-1]["id"]], "scene": scene,
                 "speech_end": round(start + dur, 3)}
        if shown:
            entry["spoken"] = text
        sentences.append(entry)
        spoken_seconds += dur
    audio += silence(1.0)

    flat_wav = os.path.join(args.out, "voiceover-flat.wav")
    with wave.open(flat_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(audio))
    final = os.path.join(args.out, "voiceover.wav")
    # One level for the whole narration; the length must not change, so no time-stretching filters.
    code, _, err = run(["ffmpeg", "-v", "error", "-y", "-i", flat_wav, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                        "-ar", str(RATE), "-ac", "1", "-c:a", "pcm_s16le", final], timeout=600)
    if code != 0:
        fail("could not level the voiceover", detail=err.strip()[-200:])
    os.remove(flat_wav)

    for name, data in (("words.json", words), ("sentences.json", sentences)):
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    total_words = sum(len(t.split()) for _, t in flat)
    summary = {"engine": args.engine, "voice": voice, "language": language, "passages": len(flat),
               "newly_spoken": made, "duration": round(probe(final)["duration"], 2),
               "speech_seconds": round(spoken_seconds, 1), "words": total_words,
               "words_per_minute": round(total_words / spoken_seconds * 60),
               "voiceover": os.path.abspath(final), "note": NOTES[args.engine],
               **({"model": model, "voice_verified_for_language_on_model": verified} if model else {}),
               "next": "You cannot hear it: run transcribe.py on voiceover.wav with the narration as --script; "
                       "a low match rate means the voice misreads the text."}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
