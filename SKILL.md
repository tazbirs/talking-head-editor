---
name: talking-head-editor
description: Fully edit a raw talking-head video into a finished, professionally edited YouTube MP4 - dynamic zooms and reframing, split-screen and picture-in-picture layouts, script-synced motion graphics, Bangla and English kinetic typography, sound effects and a quality-checked H.264 export. Use this skill whenever the person gives raw footage of someone speaking (with or without a script) and asks to edit it, make it engaging, add motion graphics, captions, zooms, b-roll or sound design, or says things like "edit my video", "edit this like a pro", "make this YouTube ready", "ভিডিও এডিট করো" - even when they do not name any tool. This is the entry point for talking-head edits; it drives the hyperframes and remotion-motion-graphics skills, so start here rather than with those.
---

# Talking-head editor

Turn one raw clip of a person speaking into a finished edit that looks like an editor spent hours in Premiere and After Effects. The person supplies the footage and, usually, the script of what they say (Bangla, English, or a mix). You deliver a rendered MP4, not a plan.

What the person wants, in their words: make the creative decisions yourself, do not ask them to pick each zoom or sound, and do not stop after analysis or planning. So this skill runs without stops: where the HyperFrames skill says to pause for a story pick or a preview approval, carry on, and report at the end what you chose.

## How the pieces fit

| Job | Tool | Why this one |
| --- | --- | --- |
| Word timings | `scripts/transcribe.py` (Whisper large-v3) | Covers Bangla and English; Parakeet does not cover Bangla |
| Layouts, zooms, graphics, all on-screen text | HyperFrames (`/hyperframes:hyperframes`) | Renders through Chrome, which shapes Bengali conjuncts correctly |
| Motion craft (easing, stagger, exits) | `remotion-motion-graphics` skill, as a rulebook only | Its ten motion rules apply to any engine; do not start a second renderer |
| Probing, cutting, audio measurement, final checks | FFmpeg / ffprobe, `scripts/probe.py`, `scripts/qc.py` | |
| Glue | Python 3 and Node.js | |

Never draw text with FFmpeg (`drawtext`, `subtitles`): this machine's build has no text filters, and FFmpeg breaks Bengali shaping anyway.

Run commands with `/opt/homebrew/bin` and `~/.local/bin` on `PATH`. `SKILL_DIR` below means the folder this file is in.

## Step 0 - Tools up to date

```bash
python3 "$SKILL_DIR/scripts/check_updates.py"
```

It checks at most once a day, stable releases only, and prints JSON. Act on `action`:

- `none`: carry on.
- `apply`: run `python3 "$SKILL_DIR/scripts/check_updates.py" --apply` before any render, then read `references/updates.md` for what to do after a significant update. The person gave standing permission for these updates, including the HyperFrames plugin, so the plugin's own "do not update the plugin yourself" note does not apply here.
- `review_remotion` (as the action, or `"review_remotion": true` beside another action): the Remotion skill changed upstream. It is instructions from one individual's repository, so it is reviewed, never auto-installed: follow `references/updates.md`.

If the check cannot reach the network, edit with the installed versions and say so in the delivery note. A failed update never blocks an edit.

## Step 1 - Take in the footage

1. Make a project folder beside the footage: `<video name>-edit/`. Never modify or move the original.
2. `python3 "$SKILL_DIR/scripts/probe.py" <video>` and keep its JSON. It gives resolution, frame rate, duration, and flags to act on:
   - `hdr: true` (phone HLG/PQ footage): convert to SDR first, or the edit looks washed out.
   - `variable_frame_rate: true` or `keyframe_interval_s > 1`: HyperFrames freezes on sparse keyframes; let `init --video` re-encode, or re-encode with `-g <fps>`.
   - `rotation`: bake it in before anything else.
3. Scaffold: `hyperframes init <dir> --video <video> --skip-skills --skip-transcribe --non-interactive --skill=hyperframes`, with `--resolution landscape-4k` (or the matching preset) when the source is 4K. The canvas and the render `--fps` match the source; the person asked for original resolution and frame rate.
4. Look at the person: extract four or five frames spread through the clip and read them. Write down, as fractions of the frame, where the face and the upper body sit (`face_box`), which side has empty space, and what the background and lighting are like. Every later reframe depends on this.

## Step 2 - Words and timing

```bash
python3 "$SKILL_DIR/scripts/transcribe.py" <video> --out <dir>/transcript \
  --language bn|en --script <script file>
```

- Pass `--language` whenever you know it. A Bangla video with English terms is `bn`. Leave it out only for truly unknown audio.
- With `--script`, the script's own spelling is kept and Whisper only supplies the timing, which is what makes Bangla captions trustworthy. Without a script, Whisper's text is used: tell the person the Bangla spelling is unverified.
- Read the summary it prints. `match_rate` under about 0.6 means the script and the speech disagree (ad-libs, a different take, or weak recognition): check `sentences.json` against the audio at a few points before building on it, and say so at delivery.
- The first run downloads the large-v3 model (about 3 GB).

Outputs: `words.json` (`id`, `text`, `start`, `end`, `how`) and `sentences.json`. Both are the clock for everything that follows: a graphic lands on the word that says it.

## Step 3 - The edit plan

Read `references/edit-plan.md`, then write `<dir>/edit-plan.json`: one entry per beat, sentence by sentence, each with its emotion, layout, camera move, graphic and sound. That file holds the rules that keep an edit from looking templated: how often to change layout, how far a punch-in may go before the face softens, which emotion earns which treatment, and when to leave a sentence alone.

Two rules matter more than the rest:

- **Every graphic is caused by the words.** If the sentence does not name it, it does not appear. A sentence of plain explanation gets a quiet camera move and nothing else.
- **Real things come from their source.** A named website is a real capture (`hyperframes capture <url>`), a named tool's logo comes through `/hyperframes:media-use`, never a redrawn one. Do not invent a software interface or show a feature you have not verified exists; when there is no source, use an abstract diagram or type instead.

## Step 4 - Build

Read `/hyperframes:hyperframes` (the contract) and its `references/overlays.md` (video rectangles for split and picture-in-picture, card timing), then build:

- The footage is one `<video class="clip" data-has-audio="true">` in the root, inside a wrapper. Layout changes and zooms are GSAP transforms on the wrapper, with `transform-origin` at the face so a zoom never slides the face out of frame.
- One sub-composition per chapter of the plan, so no track gets crowded and chapters can be fixed alone.
- Search the registry (`/hyperframes:hyperframes-registry`) before hand-building any named effect.
- Type: read `references/typography.md`. Bengali fonts are bundled in `assets/fonts/` of this skill; copy the ones you use into the project and declare them with `@font-face`, because HyperFrames resolves only its own bundled Latin families by name.
- Motion: apply the ten rules in the `remotion-motion-graphics` skill (eased or sprung motion, two or three properties per entrance, staggered arrivals, exits faster than entrances). Ignore its Remotion setup and render steps.
- Sound: read `references/sound.md`. The voice stays dominant; effects are few and each has a cause on screen.

## Step 5 - Check before rendering

1. `hyperframes check --json`; fix every error.
2. `hyperframes snapshot --at <times>` at the midpoint of every beat that changes the picture, and read the PNGs. This is the only way you see the video. Look for, in this order: Bengali text with broken or separated letters, a cropped or squashed face, text outside the title-safe area or over the face, a graphic on the wrong sentence, the same zoom twice in a row.
3. Fix and re-snapshot until a pass is clean.

## Step 6 - Render and verify

```bash
hyperframes render --quality delivery --fps <source fps> -o <dir>/out/<name>-edited.mp4
python3 "$SKILL_DIR/scripts/qc.py" --source <video> --output <mp4> --plan <dir>/edit-plan.json
```

A long video renders slowly: run it detached as the HyperFrames CLI skill describes, and tell the person roughly how long it will take.

`qc.py` verifies what the person asked to be preserved (resolution, frame rate, duration, H.264 + AAC), measures whether the voice has drifted out of sync with the original, measures loudness and true peak, and writes contact sheets of frames at every beat. Read its JSON and look at every contact sheet. Any `fail` is fixed and re-rendered before delivery.

## Step 7 - Deliver

Give the path of the MP4 and a short note:

- what the edit does (layouts used, roughly how many graphics, sound),
- what was measured and what was only inferred: you cannot hear, so say that sync and loudness were measured, not listened to,
- anything you could not do, plainly. If a tool or skill was unavailable, say so instead of implying it was used; if the script and the speech disagreed, say where.

## Reference files

| Read | When |
| --- | --- |
| `references/edit-plan.md` | Before writing the plan: plan format, layouts, camera limits, emotion table, density |
| `references/typography.md` | Before any on-screen text: Bangla and English fonts, sizes, shaping checks |
| `references/sound.md` | Before placing audio: sources, levels, which sound goes with which action |
| `references/updates.md` | When Step 0 reports `apply` or `review_remotion`, or a tool misbehaves after an update |
| `references/tool-notes.md` | Always, briefly: commands or behaviours that changed in a tool release since this skill was written |
