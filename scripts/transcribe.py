#!/usr/bin/env python3
"""Word-level timings for a talking-head clip, optionally aligned to the person's script.

usage: transcribe.py <media> [<media> ...] --out <dir> [--language bn|en|...] [--script <file>]
                     [--terms "Name One, Name Two"] [--model large-v3|medium|small|tiny]
                     [--by-line] [--lines <on-screen lines file>]

Several media files are joined in the order given (a narration recorded in parts).

--by-line is for a narration that will drive a video with no footage: sentences.json then
has one entry per line of the script (not per sentence), with its scene, each lasting until
the next line starts, and <dir>/voiceover.wav is written (48 kHz mono, levelled). That is the
same output as voice.py, so the video is built the same way from a recording or a generated
voice. --lines swaps in the matching on-screen lines as the text.

Uses mlx-whisper on Apple Silicon and whisper-ctranslate2 everywhere else.

Writes <dir>/words.json      [{id, text, start, end, how}]
       <dir>/sentences.json  [{id, text, start, end, words: [first_id, last_id]}]
       <dir>/whisper.json    Whisper's raw output
and prints a JSON summary.

With --script, the text is the script's (its spelling is trusted) and Whisper only
supplies timing. `how` says where each word's timing came from:
  exact  - the same word was recognised
  fuzzy  - matched by characters inside a stretch Whisper heard differently
  interp - not recognised; spread between its neighbours' times
"""
import argparse
import difflib
import json
import os
import re
import sys
import unicodedata

from common import need, probe, run, run_whisper, whisper_backend, whisper_install_hint

SENTENCE_END = "।.?!\n"
STRIP = re.compile(r"[^\wঀ-৿]+", re.UNICODE)


def norm(word):
    """Comparison form: NFC, lower-case, no punctuation, no zero-width joiners."""
    w = unicodedata.normalize("NFC", word).lower().replace("‌", "").replace("‍", "")
    return STRIP.sub("", w)


def whisper_words(raw):
    out = []
    for seg in raw.get("segments", []):
        for w in seg.get("words", []) or []:
            text = w.get("word", "").strip()
            if text and w.get("end", 0) >= w.get("start", 0):
                out.append({"text": text, "start": float(w["start"]), "end": float(w["end"])})
    return out


def split_script(text):
    """Script -> [(word, ends_sentence)]. Lines in brackets are stage directions and are skipped."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\[(（].*?[\])）]", " ", text)
    tokens = []
    for line in text.splitlines():
        parts = line.split()
        for i, tok in enumerate(parts):
            if not norm(tok):
                if tokens and any(c in SENTENCE_END for c in tok):
                    tokens[-1] = (tokens[-1][0], True)
                continue
            ends = tok[-1] in SENTENCE_END or i == len(parts) - 1
            tokens.append((tok, ends))
    return tokens


def split_by_line(text):
    """Script -> ([(word, ends_line)], [scene of each line], [each line's text]). Brackets are notes."""
    text = unicodedata.normalize("NFC", text)
    tokens, scenes, lines, scene, blank = [], [], [], 0, False
    for raw in text.splitlines():
        line = " ".join(re.sub(r"[\[(（].*?[\])）]", " ", raw).split())
        words = [w for w in line.split() if norm(w)]
        if not words:
            blank = blank or bool(lines)
            continue
        if blank:
            scene += 1
            blank = False
        for i, w in enumerate(words):
            tokens.append((w, i == len(words) - 1))
        scenes.append(scene)
        lines.append(line)
    return tokens, scenes, lines


def spread(weights, t0, t1):
    """(start, end) pairs between t0 and t1, each as long as its weight (a word's length)."""
    if not weights:
        return []
    t1 = max(t1, t0)
    total = float(sum(weights)) or 1.0
    out, acc = [], 0.0
    for w in weights:
        out.append((t0 + (t1 - t0) * acc / total, t0 + (t1 - t0) * (acc + w) / total))
        acc += w
    return out


def align_gap(script_words, heard):
    """Timing for script words inside a stretch where no whole word matched.

    Matches by characters: each heard word's time is spread over its characters, the
    script's characters are aligned to them, and a script word takes the span of its
    matched characters. Returns [(start, end) or None] per script word.
    """
    h_chars, h_times = [], []
    for w in heard:
        chars = norm(w["text"])
        for k, c in enumerate(chars):
            h_chars.append(c)
            h_times.append(w["start"] + (w["end"] - w["start"]) * (k + 0.5) / len(chars))
    s_chars, s_owner = [], []
    for idx, w in enumerate(script_words):
        for c in norm(w):
            s_chars.append(c)
            s_owner.append(idx)
    spans = [None] * len(script_words)
    if not h_chars or not s_chars:
        return spans
    sm = difflib.SequenceMatcher(None, s_chars, h_chars, autojunk=False)
    hits = [[] for _ in script_words]
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            hits[s_owner[a + k]].append(h_times[b + k])
    for idx, w in enumerate(script_words):
        # Trust a word only when at least half of its characters were found.
        if hits[idx] and len(hits[idx]) * 2 >= len(norm(w)):
            spans[idx] = (min(hits[idx]), max(hits[idx]))
    return spans


def align(script_tokens, heard):
    s_norm = [norm(w) for w, _ in script_tokens]
    h_norm = [norm(w["text"]) for w in heard]
    timing = [None] * len(script_tokens)
    how = ["interp"] * len(script_tokens)

    sm = difflib.SequenceMatcher(None, s_norm, h_norm, autojunk=False)
    blocks = sm.get_matching_blocks()
    for a, b, size in blocks:
        for k in range(size):
            timing[a + k] = (heard[b + k]["start"], heard[b + k]["end"])
            how[a + k] = "exact"

    # Stretches between exact anchors: try character matching.
    prev_a = prev_b = 0
    for a, b, size in blocks:
        if a > prev_a and b > prev_b:
            spans = align_gap([w for w, _ in script_tokens[prev_a:a]], heard[prev_b:b])
            for k, span in enumerate(spans):
                if span:
                    timing[prev_a + k] = span
                    how[prev_a + k] = "fuzzy"
        prev_a, prev_b = a + size, b + size

    # A match far from where the word should fall is a coincidence (a common word matched in
    # the wrong place after the recogniser skipped a stretch), and one such anchor drags every
    # word around it. Speech runs at a roughly even pace, so each word has an expected time.
    if heard and len(script_tokens) > 30:
        t_first, t_last = heard[0]["start"], heard[-1]["end"]
        sizes = [max(1, len(n)) for n in s_norm]
        whole, acc, tol = float(sum(sizes)), 0.0, max(6.0, 0.05 * (t_last - t_first))
        for idx, size in enumerate(sizes):
            expected = t_first + (t_last - t_first) * acc / whole
            acc += size
            if timing[idx] is not None and abs(timing[idx][0] - expected) > tol:
                timing[idx], how[idx] = None, "interp"

    # Whatever is left: spread between the nearest timed neighbours.
    total = heard[-1]["end"] if heard else 0.0
    i = 0
    while i < len(timing):
        if timing[i] is not None:
            i += 1
            continue
        j = i
        while j < len(timing) and timing[j] is None:
            j += 1
        t0 = timing[i - 1][1] if i > 0 else (heard[0]["start"] if heard else 0.0)
        t1 = timing[j][0] if j < len(timing) else total
        for k, span in enumerate(spread([max(1, len(n)) for n in s_norm[i:j]], t0, t1)):
            timing[i + k] = span
        i = j

    # Keep times in order and give every word a visible length.
    words, last = [], 0.0
    for idx, (tok, _) in enumerate(script_tokens):
        start, end = timing[idx]
        start = max(start, last)
        end = max(end, start + 0.04)
        last = start
        words.append({"id": "w%d" % idx, "text": tok, "start": round(start, 3),
                      "end": round(end, 3), "how": how[idx]})
    return words


def pauses(wav):
    """Ends of the silences in a file: the moments speech resumes."""
    code, _, err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af", "silencedetect=noise=-38dB:d=0.22",
                        "-f", "null", "-"], timeout=900)
    return [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", err)]


def sentences_from(words, ends):
    out, first = [], 0
    for i, w in enumerate(words):
        if ends[i] or i == len(words) - 1:
            chunk = words[first:i + 1]
            out.append({"id": "s%d" % len(out), "text": " ".join(x["text"] for x in chunk),
                        "start": chunk[0]["start"], "end": chunk[-1]["end"],
                        "words": [chunk[0]["id"], chunk[-1]["id"]]})
            first = i + 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("media", nargs="+")
    ap.add_argument("--by-line", action="store_true", help="one sentence per script line, plus voiceover.wav")
    ap.add_argument("--lines", help="on-screen lines file matching the script line for line (with --by-line)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--language", help="ISO code such as bn or en; omit only for unknown audio")
    ap.add_argument("--script", help="text file with what the speaker says")
    ap.add_argument("--model", default="large-v3",
                    help="large-v3 (default), medium, small or tiny; on a CPU-only machine medium is much faster")
    ap.add_argument("--terms", help="a few names or technical terms to help spelling, e.g. 'HyperFrames, Kling AI'")
    args = ap.parse_args()

    need("ffmpeg")
    if whisper_backend() is None:
        raise SystemExit(json.dumps({"error": "No Whisper is installed.", "fix": whisper_install_hint()}))
    os.makedirs(args.out, exist_ok=True)
    for m in args.media:
        if probe(m).get("audio_codec") is None:
            raise SystemExit(json.dumps({"error": "%s has no audio track" % m}))
    # One file, or several joined in order. 48 kHz for the film, 16 kHz for Whisper.
    full = os.path.join(args.out, "joined-48k.wav")
    inputs = [x for m in args.media for x in ("-i", m)]
    chain = "".join("[%d:a]" % i for i in range(len(args.media))) + "concat=n=%d:v=0:a=1[a]" % len(args.media)
    code, _, err = run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", chain, "-map", "[a]",
                        "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", full], timeout=1800)
    if code != 0:
        raise SystemExit(json.dumps({"error": "could not read the audio", "detail": err[-400:]}))
    info = probe(full)
    wav = os.path.join(args.out, "audio-16k.wav")
    code, _, err = run(["ffmpeg", "-v", "error", "-y", "-i", full, "-ac", "1", "-ar", "16000", wav], timeout=1800)
    if code != 0:
        raise SystemExit(json.dumps({"error": "could not extract audio", "detail": err[-400:]}))

    script_text = None
    if args.script:
        with open(args.script, encoding="utf-8") as f:
            script_text = f.read()

    # Never prime Whisper with the script itself: given the words it is about to hear, it
    # treats them as already transcribed and skips the speech (measured: 3 of 45 words heard).
    # A short list of names and terms (--terms) is safe.
    # Allow well over real time: a CPU-only machine is slow, and the first run downloads the model.
    raw_path, error = run_whisper(wav, args.out, "whisper", model=args.model, language=args.language,
                                  terms=args.terms, timeout=int(info["duration"] * 6) + 3600)
    if error:
        raise SystemExit(json.dumps({"error": error}))
    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)
    heard = whisper_words(raw)
    if not heard:
        raise SystemExit(json.dumps({"error": "whisper found no speech"}))

    summary = {"language": raw.get("language"), "duration": info["duration"],
               "heard_words": len(heard), "model": args.model, "engine": whisper_backend()}
    line_scenes = line_texts = None
    if args.by_line and not script_text:
        raise SystemExit(json.dumps({"error": "--by-line needs --script: the narration, one passage per line"}))
    if script_text:
        if args.by_line:
            tokens, line_scenes, line_texts = split_by_line(script_text)
        else:
            tokens = split_script(script_text)
        words = align(tokens, heard)
        ends = [e for _, e in tokens]
        counts = {k: sum(1 for w in words if w["how"] == k) for k in ("exact", "fuzzy", "interp")}
        rate = (counts["exact"] + counts["fuzzy"]) / max(1, len(words))
        summary.update({"script_words": len(words), "timing_from": counts, "match_rate": round(rate, 3)})
        if rate < 0.6:
            summary["warning"] = ("Under 60% of the script was found in the speech. The script may not "
                                  "match this take, or recognition was weak: spot-check sentences.json.")
        if words and words[-1]["end"] > info["duration"]:
            summary["warning_end"] = "The last word ends past the media: clamp to the file's duration."
    else:
        words = [{"id": "w%d" % i, "text": w["text"], "start": round(w["start"], 3),
                  "end": round(w["end"], 3), "how": "heard"} for i, w in enumerate(heard)]
        ends = [w["text"][-1] in SENTENCE_END for w in words]
        summary["note"] = "No script given: the text is Whisper's own and its spelling is unverified."

    sentences = sentences_from(words, ends)
    if args.by_line:
        shown = None
        if args.lines:
            with open(args.lines, encoding="utf-8") as f:
                _, shown_scenes, shown = split_by_line(f.read())
            if shown_scenes != line_scenes:
                raise SystemExit(json.dumps({"error": "The script and the on-screen lines do not match line for line.",
                                             "script_lines": len(line_scenes), "screen_lines": len(shown_scenes)}))
        # A new passage starts after a pause: move each start onto the nearest moment speech resumes.
        resumes = pauses(wav)
        for sent in sentences[1:]:
            near = [t for t in resumes if abs(t - sent["start"]) <= 0.9]
            if near:
                sent["start"] = round(min(near, key=lambda t: abs(t - sent["start"])), 3)
        for a_, b_ in zip(sentences, sentences[1:]):
            b_["start"] = max(b_["start"], round(a_["start"] + 0.3, 3))
        for i, sent in enumerate(sentences):
            sent["scene"] = line_scenes[i]
            sent["speech_end"] = sent["end"]
            # A passage holds the screen until the next one starts; the last one until the audio ends.
            sent["end"] = sentences[i + 1]["start"] if i + 1 < len(sentences) else round(info["duration"], 3)
            if shown:
                sent["spoken"], sent["text"] = line_texts[i], shown[i]
        voiceover = os.path.join(args.out, "voiceover.wav")
        code, _, err = run(["ffmpeg", "-v", "error", "-y", "-i", full, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", voiceover], timeout=1800)
        if code != 0:
            raise SystemExit(json.dumps({"error": "could not level the voiceover", "detail": err[-300:]}))
        summary["voiceover"] = os.path.abspath(voiceover)
        weak = [s_["id"] for s_ in sentences
                if all(w["how"] == "interp" for w in words[int(s_["words"][0][1:]):int(s_["words"][1][1:]) + 1])]
        if weak:
            summary["unanchored_lines"] = len(weak)
            summary["warning_lines"] = ("%d line(s) had no recognised word, so their start is estimated from "
                                        "their neighbours: check those moments." % len(weak))
    os.remove(full)
    for name, data in (("words.json", words), ("sentences.json", sentences)):
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    summary.update({"sentences": len(sentences), "out": os.path.abspath(args.out)})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
