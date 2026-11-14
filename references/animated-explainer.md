# Animated explainer mode

For a video with no footage of a speaker: an explainer, a "how it works", a topic discussed in pictures. The person gives a topic or a script, in Bangla or English, and sometimes a recorded voiceover. You deliver a fully animated MP4.

The HyperFrames skill already knows how to make a good explainer. Read its `references/types/explainer.md` and `references/story.md` and follow them. This file adds what they do not cover: where the script and the voice come from, how timing is set without footage, Bangla, and the checks.

What this mode is good at: type, diagrams that build, charts, maps, real screenshots and logos, icons, numbers. What it is not good at: characters that walk, talk and act like a cartoon. If the request needs that, say so before starting and offer the motion-graphics version.

## 1. What you were given decides the path

| Given | Do |
| --- | --- |
| A finished script | Use it word for word. No stop. |
| A script and a voiceover recording | The recording is the clock (section 3). No stop. |
| Only a topic | Research it, write the script (section 2), show it and wait once for a yes. |

The one stop for a topic-only request exists because the script is what the person publishes under their name, and fixing a sentence costs seconds before the build and a full re-render after it. If they said "no stops" or "just make it", skip the stop and put the script and its sources in the delivery note instead.

## 2. Writing the script from a topic

- **Find the one idea** the viewer should understand at the end, and one concrete example to carry it from the first second to the last (`story.md` section 1). A list of facts about the topic is not an explainer.
- **Every factual claim has a source.** Look it up; do not write from memory for numbers, dates, prices, names, limits or "how X works" claims. Keep `SOURCES.md` in the project: each claim, where it came from, the date you read it. A claim you cannot source is cut or said as uncertain.
- **Current things change.** For tools, prices, free tiers and features, check the official page on the day. Never show a feature or an interface you have not verified.
- **Length:** 30-90 s is the natural size (about 70-200 spoken Bangla words). Longer topics become chapters, each with its own idea. Say the length you chose.
- **Language:** write in the language the person asked in. Bangla scripts keep technical terms in English as a Bangla speaker would say them.
- **Shape:** a question the viewer would ask, the example worked through, the answer in one line. About 19 spoken words per scene.
- Write narration and on-screen lines separately. The screen never repeats the narration word for word.

Show the person: the one idea, the script, the length, and whether it will be narrated. Then wait for the yes.

## 3. The clock: where timing comes from

| Voice | Clock | Command |
| --- | --- | --- |
| The person's recording | Their speech | `transcribe.py <audio> --out <dir>/transcript --language bn --script <script>` |
| No voice | Reading pace of the on-screen lines | `pace.py <lines file> --out <dir>/transcript` |
| A generated voice | The generated audio, then as a recording | `/hyperframes:media-use` (`--type voice`), then `transcribe.py` |

- `transcribe.py` takes an audio file as well as a video.
- `pace.py` reads a text file with one on-screen line per line and a blank line between scenes, and gives each line `0.5 s + 0.3 s a word` (HyperFrames' reading pace), slightly longer for Bangla. It writes the same `words.json` and `sentences.json` as `transcribe.py`, so everything downstream is identical.
- **Generated voices and Bangla:** do not assume a Bangla voice exists. Check what `/hyperframes:media-use` offers for the language; the local voice (Kokoro) is not a Bangla voice. If there is no good Bangla voice, say so and offer the two honest options: the person records the script themselves (best result), or an unnarrated video carried by type and music. Never deliver an English-accented or wrong-language voice reading Bangla.
- Without a voice, the type carries the meaning: lines are large, up to about 10 words, and music matters more (`sound.md`).

## 4. Plan

Write `edit-plan.json` in the same format as `edit-plan.md` describes, with these differences:

- `source` is `{"width": 1920, "height": 1080, "fps": "30/1", "duration": <clock length>}`: 1920x1080 at 30 fps unless asked otherwise; 1080x1920 for a vertical short.
- There is no `face_box`, and every beat's `layout` is `graphics`.
- Each beat has a `visual` instead of a camera move: the device from `types/explainer.md` it uses (`object`, `growing-diagram`, `transformation`, `worked-example`, or a shape such as `number-lands`, `before-after`, `steps`, `screenshot-detail`), what appears, and which word it appears on.
- `graphic.source` keeps the same rule: `type`, `diagram`, `capture`, `logo` or `person`. Real things come from their source.

Rules that matter most here:

- One idea per scene, and the picture changes every 4-8 s.
- A diagram grows one part per beat, each part appearing when it is named. Never the whole diagram at once.
- One look for the whole video: one ground, one accent, one Bangla family and one Latin family (`typography.md`). Choose the look from the subject, not a default dark gradient.
- Avoid the tells: a slide of bullets, icons in circles, three cards in a row.
- **The first frame is the thumbnail.** The opening line and its picture are already on screen at 0 s and only settle; an entrance that starts from nothing leaves an empty first frame (`check` reports `first_frame_empty`).
- **Use the whole frame.** Size the picture to the canvas: the main device fills roughly the middle 60% of the height, and labels are at least 40 px. Text in the top corner with the rest empty reads as a slide, not a film. Look for this in the snapshots.

## 5. Build, check, render

Build as the HyperFrames skill describes: one sub-composition per scene, registry blocks before hand-built effects, the Bengali fonts copied from this skill and declared with `@font-face`. With a voice, the audio file is an `<audio>` with an `id` in the root.

Then the same loop as any edit: `check --json`, snapshots at the midpoint of every scene, look at each one, fix, render.

```bash
python3 "$SKILL_DIR/scripts/qc.py" --output <mp4> --plan <dir>/edit-plan.json \
  --expect 1920x1080@30 [--voice <voiceover file>]
```

With `--voice` it measures whether the narration in the render still lines up with the recording. A video with no audio track passes with a warning: add sound (`sound.md`) or say plainly at delivery that it is silent. Read the JSON and look at every contact sheet.

## 6. Deliver

The MP4 path and a short note: the one idea, the length, how it was voiced, the sources file, what was measured rather than heard, and anything you could not do (no Bangla voice, a screenshot you could not capture, a claim you cut for lack of a source).
