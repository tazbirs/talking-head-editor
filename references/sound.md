# Sound

You cannot hear the result, so sound is placed by rule and verified by measurement. The HyperFrames skill's `references/sound.md` is the base; this file adds what a talking-head edit needs.

## The voice comes first

- The speaker's original audio is the footage's own track (`data-has-audio="true"`). Do not replace, re-time, denoise or re-level it unless the person asks; any processing risks sync and naturalness.
- Everything else sits under it. Music under speech at about 0.10-0.14 volume; effects 3-6 dB above the music, still below the voice.
- Nothing lands on top of a stressed word unless it is the word's own graphic arriving.

## Where sounds come from

Use `/hyperframes:media-use` (`--type sfx`, `--type bgm`). This skill runs without stops, so:

- Effects: take the free sources that need no sign-in (bundled and Openverse). Openverse files are CC BY: collect the credits into `<dir>/CREDITS.txt` and mention it at delivery so the person can paste them in the video description.
- Music: only when the video suits it, and only from a real source. Check `hyperframes auth status`; when the person is not signed in, deliver without music and say in one line that signing in to HyperFrames (free) opens the music catalog. Do not write music in code and do not synthesise tones or chimes: nobody in the loop can judge them.
- The person's own files always win. If the project folder has an `sfx/` or `music/` folder, use those first.

## Which sound, when

| Sound | Only on |
| --- | --- |
| Whoosh | A layout change, or a large element moving fast |
| Pop | A badge, chip, icon or number landing |
| Click | A cursor click shown on screen |
| UI tick | Text arriving line by line, list items |
| Notification | A notification or message graphic |
| Soft impact / bass hit | An important word or statement landing |
| Riser into impact | The main reveal, once per video |

- Each sound has a visible cause. No cause, no sound.
- Place a sound so its peak lands one frame after the picture it belongs to; `hyperframes audio <file> --json` reports where a file peaks.
- Rotate two or three takes of a repeated sound. The same whoosh on every transition is the most recognisable sign of a templated edit.
- Fewer than the plan first suggests. On a long video, aim for effects on the moments that matter, not on every graphic.

## Levels and checks

- Each added file: true peak at -1 dBTP or lower (`hyperframes normalize-audio`).
- The final mix: `qc.py` reports integrated loudness and true peak. Around -16 to -14 LUFS is right for YouTube; a true peak above -1 dBTP fails.
- `qc.py` also compares the voice in the output with the source and reports any offset. More than about 40 ms is a sync fault: fix before delivery.
- In the delivery note, say that loudness and sync were measured, not heard.
