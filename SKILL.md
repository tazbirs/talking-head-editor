---
name: talking-head-editor
description: Make a finished, professionally edited YouTube video in Bangla or English, in one of two ways. (1) Edit raw talking-head footage - dynamic zooms and reframing, split-screen and picture-in-picture layouts, script-synced motion graphics, kinetic typography, sound effects, quality-checked H.264 export. (2) Make a fully animated explainer with no footage, from a topic or a script, with or without a recorded voiceover. Use this skill whenever the person gives footage of someone speaking and asks to edit it, make it engaging, or add motion graphics, captions, zooms or sound design; whenever they ask for an explainer, an animated video, a "how it works" or a video about a topic; and whenever a video needs Bangla text. Phrases like "edit my video", "make this YouTube ready", "make an explainer about X", "ভিডিও এডিট করো", "এই টপিকে একটা ভিডিও বানাও" should all trigger it, even when no tool is named. This is the entry point for these videos; it drives the hyperframes and remotion-motion-graphics skills, so start here rather than with those.
---

# Talking-head editor

Two kinds of job come through this skill. Decide which one this is first:

- **There is footage of a person speaking** to edit: follow the steps in this file.
- **There is no footage** (an explainer, an animated video, a topic to discuss in pictures): do Step 0 below, then follow `references/animated-explainer.md` instead of Steps 1-8. Typography, sound, updates and the tool table still apply. In this mode, always ask the person about the voice before building (`references/voice.md`): record it themselves, a generated voice, or none. This is the one question that is asked even when they want no stops. Before the export, the video opens in the editor for them, as in Step 6.

The rest of this file describes the footage edit. Turn one raw clip of a person speaking into a finished edit that looks like an editor spent hours in Premiere and After Effects. The person supplies the footage and, usually, the script of what they say (Bangla, English, or a mix). You deliver a rendered MP4, not a plan.

What the person wants, in their words: make the creative decisions yourself, do not ask them to pick each zoom or sound, and do not stop after analysis or planning. So this skill runs without stops: where the HyperFrames skill says to pause for a story pick, carry on, and report at the end what you chose. There is one planned stop, which the person asked for: before the final export, the finished video opens in the HyperFrames editor in their browser so they can watch it and adjust anything by hand (Step 6).

## How the pieces fit

| Job | Tool | Why this one |
| --- | --- | --- |
| Word timings | `scripts/transcribe.py` (Whisper large-v3: `mlx-whisper` on Apple Silicon, `whisper-ctranslate2` elsewhere) | Covers Bangla and English; Parakeet does not cover Bangla |
| Layouts, zooms, graphics, all on-screen text | HyperFrames (`/hyperframes:hyperframes`) | Renders through Chrome, which shapes Bengali conjuncts correctly |
| Motion craft (easing, stagger, exits) | `remotion-motion-graphics` skill, as a rulebook only | Its ten motion rules apply to any engine; do not start a second renderer |
| Probing, cutting, audio measurement, final checks | FFmpeg / ffprobe, `scripts/probe.py`, `scripts/qc.py` | |
| Narration for a video with no speaker | `scripts/voice.py` (generated voice) or the person's own recording | Natural English locally; natural Bangla needs the person's recording or an online voice they choose |
| Glue | Python 3 and Node.js | |

Never draw text with FFmpeg (`drawtext`, `subtitles`): many builds ship without text filters, and FFmpeg does not shape Bengali reliably.

The skill runs on macOS, Linux and Windows. The scripts find their tools and pick the right Whisper engine and package manager themselves; `references/platforms.md` has what differs per system and what to install when something is missing. `SKILL_DIR` below means the folder this file is in. Commands are written with `python3`; on Windows use `python`.

## Step 0 - Tools up to date

```bash
python3 "$SKILL_DIR/scripts/check_updates.py"
```

It checks at most once a day, stable releases only, and prints JSON. Act on `action`:

- `none`: carry on.
- `apply`: run `python3 "$SKILL_DIR/scripts/check_updates.py" --apply` before any render, then read `references/updates.md` for what to do after a significant update. The person gave standing permission for these updates, including the HyperFrames plugin, so the plugin's own "do not update the plugin yourself" note does not apply here.
- `review_remotion` (as the action, or `"review_remotion": true` beside another action): the Remotion skill changed upstream. It is instructions from one individual's repository, so it is reviewed, never auto-installed: follow `references/updates.md`.

- `manual_updates` (any action): on Linux and Windows, system packages need administrator rights, so the script reports them with the command instead of installing. Carry on with the edit and give the person those commands in the delivery note.
- `errors`: a missing tool or a Node.js older than 22 is named here; `references/platforms.md` has the install command for this system.

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
- The first run downloads the large-v3 model (about 3 GB). On a machine with no GPU, large-v3 can take several times the video's length: for a long video say so, or use `--model medium`.

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

## Step 5 - Check before the preview

1. `hyperframes check --json`; fix every error.
2. `hyperframes snapshot --at <times>` at the midpoint of every beat that changes the picture, and read the PNGs. This is the only way you see the video. Look for, in this order: Bengali text with broken or separated letters, a cropped or squashed face, text outside the title-safe area or over the face, a graphic on the wrong sentence, the same zoom twice in a row.
3. Fix and re-snapshot until a pass is clean.

## Step 6 - Show it in the editor

```bash
python3 "$SKILL_DIR/scripts/preview.py" <dir>
```

This opens the video in the HyperFrames editor (Studio) in the person's browser. Give them the link, say in a few lines what they can change there by hand, and stop: they answer "render" or tell you what to change. Read `references/preview.md` first: it has what to say, when to skip this stop (they declined it, or nobody is there to look), how to read what they clicked in the editor, and the rule that matters most afterwards: the editor writes into the HTML files, so from this point never regenerate them from a build script.

When they say render, `python3 "$SKILL_DIR/scripts/preview.py" <dir> --changes` lists what they changed by hand; re-check those scenes, keep their choices, and go on.

## Step 7 - Render and verify

```bash
hyperframes render --quality delivery --fps <source fps> -o <dir>/out/<name>-edited.mp4
python3 "$SKILL_DIR/scripts/qc.py" --source <video> --output <mp4> --plan <dir>/edit-plan.json
```

A long video renders slowly: run it detached as the HyperFrames CLI skill describes, and tell the person roughly how long it will take.

`qc.py` verifies what the person asked to be preserved (resolution, frame rate, duration, H.264 + AAC), measures whether the voice has drifted out of sync with the original, measures loudness and true peak, and writes contact sheets of frames at every beat. Read its JSON and look at every contact sheet. Any `fail` is fixed and re-rendered before delivery.

## Step 8 - Deliver

Give the path of the MP4 and a short note:

- what the edit does (layouts used, roughly how many graphics, sound),
- which files carry changes the person made by hand in the editor, if any,
- what was measured and what was only inferred: you cannot hear, so say that sync and loudness were measured, not listened to,
- anything you could not do, plainly. If a tool or skill was unavailable, say so instead of implying it was used; if the script and the speech disagreed, say where.

## Reference files

| Read | When |
| --- | --- |
| `references/edit-plan.md` | Before writing the plan: plan format, layouts, camera limits, emotion table, density |
| `references/animated-explainer.md` | When there is no footage: script from a topic, timing without a speaker, the explainer plan and checks |
| `references/voice.md` | Before building anything without a speaker: the voice question, voice engines for Bangla and English, narration writing, how to verify a voice you cannot hear |
| `references/preview.md` | Before opening the editor for the person (Step 6), and whenever they changed something there by hand |
| `references/typography.md` | Before any on-screen text: Bangla and English fonts, sizes, shaping checks |
| `references/sound.md` | Before placing audio: sources, levels, which sound goes with which action |
| `references/platforms.md` | When a tool is missing, or on any system other than an Apple Silicon Mac |
| `references/updates.md` | When Step 0 reports `apply` or `review_remotion`, or a tool misbehaves after an update |
| `references/tool-notes.md` | Always, briefly: commands or behaviours that changed in a tool release since this skill was written |
