# talking-head-editor

A Claude skill that makes finished YouTube videos in Bangla or English, two ways:

1. **Edit talking-head footage.** Dynamic zooms and reframing, split-screen and picture-in-picture layouts, motion graphics tied to what is being said, typography, sound effects, and a quality-checked H.264 export. You give Claude the raw video and, ideally, the script.
2. **Make an animated explainer with no footage.** You give a topic or a script. Claude always asks first whether you will record the narration yourself, want a generated voice, or want no voice. Claude researches and writes the script when you give only a topic (and shows it to you first), then builds the video from type, diagrams, charts and real screenshots.

Either way Claude hands back an MP4.

The explainer mode is for motion graphics. It is not for cartoon-style character animation.

## Status

Early. The helper scripts are tested (see below); the full workflow has not yet been run on real Bangla footage. Treat the first real edits as the test.

Platform support: built and tested on an Apple Silicon Mac. The scripts also handle Intel Macs, Linux (Debian/Ubuntu, Arch, Fedora, others) and Windows, but those paths have been tested only in simulation, not on those systems. Reports and fixes are welcome.

## What it uses

| Job | Tool |
| --- | --- |
| Word timings | Whisper large-v3: [`mlx-whisper`](https://github.com/ml-explore/mlx-examples/tree/main/whisper) on Apple Silicon, [`whisper-ctranslate2`](https://github.com/Softcatala/whisper-ctranslate2) everywhere else |
| Layouts, graphics and all on-screen text | [HyperFrames](https://github.com/heygen-com/hyperframes) (Claude Code plugin) |
| Motion design rules | [claude-remotion-skill](https://github.com/haidrrrry/claude-remotion-skill), used as a rulebook only |
| Probing, audio measurement, final checks | [FFmpeg](https://ffmpeg.org) |
| Glue | Python 3.9+ (standard library only), Node.js 22+ |

Whisper rather than Parakeet because Parakeet does not cover Bangla. All text is rendered by HyperFrames through Chrome, which shapes Bengali conjuncts correctly.

## Install

Three steps: system tools, a Whisper engine, then the skill and the HyperFrames plugin. You also need [Claude Code](https://claude.com/claude-code).

### 1. System tools

**macOS** (with [Homebrew](https://brew.sh))

```bash
brew install ffmpeg node@22 python@3.13 uv git
```

**Debian / Ubuntu**

```bash
sudo apt update && sudo apt install ffmpeg python3 git espeak-ng
```

Debian's own Node.js is older than 22, and uv is not in apt: install Node 22 from [NodeSource](https://github.com/nodesource/distributions) or a version manager (`fnm`, `nvm`), and uv with its [official installer](https://docs.astral.sh/uv/getting-started/installation/).

**Arch**

```bash
sudo pacman -S ffmpeg nodejs-lts-jod npm python uv git espeak-ng
```

**Fedora**

```bash
sudo dnf install ffmpeg-free nodejs python3 uv git espeak-ng
```

If the FFmpeg stage of the smoke test fails on Fedora, install the full `ffmpeg` from RPM Fusion (it has the H.264 encoder).

**Windows** (PowerShell, with winget)

```bash
winget install Gyan.FFmpeg OpenJS.NodeJS.22 Python.Python.3.13 astral-sh.uv Git.Git
```

Open a new terminal afterwards. Where this README says `python3`, use `python`.

### 2. Whisper

Mac with Apple Silicon:

```bash
uv tool install --python 3.12 mlx-whisper
```

Intel Mac, Linux, Windows:

```bash
uv tool install --python 3.12 whisper-ctranslate2
```

Without a GPU, the large-v3 model runs several times slower than real time; the skill can fall back to `medium`.

### 3. The skill and the HyperFrames plugin

```bash
git clone https://github.com/tazbirs/talking-head-editor.git ~/.claude/skills/talking-head-editor
```

On Windows the folder is `%USERPROFILE%\.claude\skills\talking-head-editor`.

```bash
claude plugin marketplace add heygen-com/hyperframes
```

```bash
claude plugin install hyperframes@hyperframes
```

The Remotion skill is installed separately from its own repository; read it before installing, as with any skill.

### 4. Check it works

```bash
python3 ~/.claude/skills/talking-head-editor/scripts/smoke_test.py
```

It encodes a clip with FFmpeg, times a spoken sentence with Whisper and renders a Bangla title with HyperFrames, then reports each stage. Start a new Claude Code session and say something like *"edit this video, the script is in script.txt"* or *"make a one-minute Bangla explainer about how frame rate works"*.

## What is in here

```
SKILL.md                   the workflow Claude follows
references/
  animated-explainer.md    the no-footage mode: script, timing, plan and checks
  voice.md                 the voice question, engines for Bangla and English, verifying a voice
  edit-plan.md             plan format, layouts, camera limits, emotion table
  typography.md            Bangla and English type, Bengali shaping checks
  sound.md                 sound sources, levels, which sound goes with which action
  platforms.md             what differs on macOS, Linux and Windows
  updates.md               how tool updates are applied and verified
  tool-notes.md            what changed in each tool release; the skill's own memory
scripts/
  probe.py                 facts about a clip (resolution, fps, HDR, keyframes)
  transcribe.py            Whisper word timings, aligned to the script's own text
  pace.py                  timings for a video with no voice, from reading pace
  voice.py                 generated voiceover and its timings (say, Kokoro, Azure, edge-tts)
  qc.py                    checks a render against its source; writes contact sheets
  smoke_test.py            proves FFmpeg, Whisper and HyperFrames still work
  check_updates.py         stable-only update check, apply and verify
  update-policy.json       how eager the updater is
assets/fonts/              Hind Siliguri, Noto Sans Bengali, Noto Serif Bengali (OFL)
```

## Voices

For a video with no speaker, Claude asks which voice you want before building.

| Option | Bangla | English | Notes |
| --- | --- | --- | --- |
| Your own recording | yes | yes | Best result. Claude gives you the narration to read and times the video to your audio. |
| Kokoro (local) | no | natural, male and female | Free, nothing leaves your machine. |
| Azure Speech | natural, male and female | natural | Official and licensed. Needs your own key in `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION`. |
| edge-tts | same voices as Azure | same | Free and needs no account, but it is an unofficial route: your call whether to publish with it. |
| macOS `say` | one synthetic female voice | several | A draft voice for checking timing. Apple licenses it for personal, non-commercial use. |

There is no natural Bangla voice that is both local and free, so for Bangla the real choices are your own recording or an online voice. Online voices send the narration text to that service.

## Updates

At the start of each run the skill checks for new **stable** releases of its tools (never nightly or pre-release builds), at most once a day. New major or minor versions are followed by a smoke test; patch releases are listed and left alone. Change that in `scripts/update-policy.json`.

| What | macOS (Homebrew) | Linux and Windows |
| --- | --- | --- |
| HyperFrames plugin, Whisper | Installed automatically | Installed automatically |
| FFmpeg, Node.js, Python, uv | Installed automatically | Reported with the exact command for you to run |

System packages on Linux and Windows need `sudo` or an administrator prompt, which the skill never answers for you; on Arch the command is always a full `sudo pacman -Syu`, because single-package upgrades are unsupported there.

The Remotion skill is a separate case: it is instructions from a single repository with no versioned releases, so a new version is downloaded for review and installed only after Claude has read the changes.

## Tested

- Script alignment on a Bangla sample with spelling drift, a spoken number and a missed word: every word timed, in order.
- End-to-end transcription with a script on synthetic English speech: 44 of 44 words matched.
- Quality check: passes a faithful re-encode; catches a wrong resolution and audio delayed by 120 ms and 300 ms, both measured correctly.
- Update check and apply: found and installed a real Node.js update, then passed the smoke test, including a Bangla title render.
- Animated explainer: a 2.5-minute, 11-scene Bangla explainer made from a script, with a real page capture and bundled sound effects, built, rendered and checked end to end. Narrated explainers and scripts written from a topic are not yet tried.
- Voices: local English (Kokoro, male and female) verified by transcribing it back; a narrated 4.5-minute render stayed in sync with its voice file to the millisecond. The Azure and edge-tts engines are written but have not been run. The only local Bangla voice (macOS) could not be verified and is a draft voice only.
- Both Whisper engines (`mlx-whisper` and `whisper-ctranslate2`) on the same clip: identical word matching.
- apt, pacman and winget version checks against sample output of those tools. Not yet run on a real Linux or Windows machine.

## Licence

MIT, see [LICENSE](LICENSE). The bundled fonts keep their own licence, below.

## Credits

Fonts in `assets/fonts/` are licensed under the SIL Open Font License 1.1; the licence texts are alongside them. HyperFrames is Apache-2.0, claude-remotion-skill is MIT, and neither is bundled here.
