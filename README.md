# talking-head-editor

A Claude skill that edits raw talking-head footage into a finished YouTube video: dynamic zooms and reframing, split-screen and picture-in-picture layouts, motion graphics tied to what is being said, Bangla and English typography, sound effects, and a quality-checked H.264 export.

You give Claude the raw video and, ideally, the script. Claude does the rest and hands back an MP4.

## Status

Early. The helper scripts are tested (see below); the full workflow has not yet been run on real Bangla footage. Treat the first real edits as the test.

## What it uses

| Job | Tool |
| --- | --- |
| Word timings | Whisper large-v3 via [`mlx-whisper`](https://github.com/ml-explore/mlx-examples/tree/main/whisper) |
| Layouts, graphics and all on-screen text | [HyperFrames](https://github.com/heygen-com/hyperframes) (Claude Code plugin) |
| Motion design rules | [claude-remotion-skill](https://github.com/haidrrrry/claude-remotion-skill), used as a rulebook only |
| Probing, audio measurement, final checks | [FFmpeg](https://ffmpeg.org) |
| Glue | Python 3 (standard library only), Node.js 22 |

Whisper rather than Parakeet because Parakeet does not cover Bangla. All text is rendered by HyperFrames through Chrome, which shapes Bengali conjuncts correctly.

## Requirements

- macOS on Apple Silicon (`mlx-whisper` needs it)
- [Homebrew](https://brew.sh) and [Claude Code](https://claude.com/claude-code)

```bash
brew install ffmpeg node@22 python@3.13 uv
```

```bash
uv tool install --python 3.12 mlx-whisper
```

```bash
claude plugin marketplace add heygen-com/hyperframes
```

```bash
claude plugin install hyperframes@hyperframes
```

The Remotion skill is installed separately from its own repository; read it before installing, as with any skill.

## Install

```bash
git clone https://github.com/tazbirs/talking-head-editor.git ~/.claude/skills/talking-head-editor
```

Start a new Claude Code session, then say something like *"edit this video, the script is in script.txt"*.

## What is in here

```
SKILL.md                   the workflow Claude follows
references/
  edit-plan.md             plan format, layouts, camera limits, emotion table
  typography.md            Bangla and English type, Bengali shaping checks
  sound.md                 sound sources, levels, which sound goes with which action
  updates.md               how tool updates are applied and verified
  tool-notes.md            what changed in each tool release; the skill's own memory
scripts/
  probe.py                 facts about a clip (resolution, fps, HDR, keyframes)
  transcribe.py            Whisper word timings, aligned to the script's own text
  qc.py                    checks a render against its source; writes contact sheets
  smoke_test.py            proves FFmpeg, Whisper and HyperFrames still work
  check_updates.py         stable-only update check, apply and verify
  update-policy.json       how eager the updater is
assets/fonts/              Hind Siliguri, Noto Sans Bengali, Noto Serif Bengali (OFL)
```

## Updates

At the start of each run the skill checks for new **stable** releases of its tools (never nightly or pre-release builds), at most once a day. New major or minor versions are installed automatically and followed by a smoke test; patch releases are listed and left alone. Change that in `scripts/update-policy.json`.

The Remotion skill is the exception: it is instructions from a single repository with no versioned releases, so a new version is downloaded for review and installed only after Claude has read the changes.

## Tested

- Script alignment on a Bangla sample with spelling drift, a spoken number and a missed word: every word timed, in order.
- End-to-end transcription with a script on synthetic English speech: 44 of 44 words matched.
- Quality check: passes a faithful re-encode; catches a wrong resolution and audio delayed by 120 ms and 300 ms, both measured correctly.
- Update check and apply: found and installed a real Node.js update, then passed the smoke test, including a Bangla title render.

## Licence

MIT, see [LICENSE](LICENSE). The bundled fonts keep their own licence, below.

## Credits

Fonts in `assets/fonts/` are licensed under the SIL Open Font License 1.1; the licence texts are alongside them. HyperFrames is Apache-2.0, claude-remotion-skill is MIT, and neither is bundled here.
