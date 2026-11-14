# Tool notes

Things learned about the installed tools, newest first. Add an entry whenever a release changes a command, flag or behaviour this skill relies on (see `updates.md`), and correct the affected file at the same time.

## 2026-11-14 - animated explainer mode

- First real run: a 12 s, three-scene Bangla explainer with no voice, paced by `pace.py`, built in HyperFrames, rendered and checked with `qc.py --expect`. Bangla conjuncts rendered correctly with the bundled Hind Siliguri.
- What the run taught: an entrance on the first line leaves an empty first frame (HyperFrames warns `first_frame_empty`), so `pace.py` now starts at 0 s; and a single-file composition with nested scenes passes `check` but warns `nested_structure_needs_subcomposition`, so use one sub-composition per scene as the reference says.
- Not yet tried: a narrated explainer with a real voiceover, a script written from a topic, music or sound effects.

## 2026-11-14 - cross-platform support

- Scripts now run on macOS (Apple Silicon and Intel), Linux and Windows. Tested for real on an Apple Silicon Mac only. The second Whisper engine (`whisper-ctranslate2`) was tested on that Mac; the apt, pacman, dnf and winget version checks were tested against sample output, not on those systems. The first run on Linux or Windows is the test: record what you find here.

## 2026-11-14 - first automatic update

- Node.js 22.22.1 to 22.23.5 through `check_updates.py --apply`; smoke test passed.
- Side effect: the upgrade moved the shared `simdjson` library and broke a second, unrelated Homebrew `node` (25.8.1), which was repaired by upgrading it to 26.13.1. `--apply` now runs `brew linkage --test` after every update and repairs what it finds.
- Two Node installs exist: `node@22` (used by the person's shell and by these scripts) and the unversioned `node` linked at `/opt/homebrew/bin/node`. Run HyperFrames on Node 22; `common.py` puts it first on `PATH`.

## 2026-11-14 - baseline (skill written)

Versions this skill was written and tested against: FFmpeg 9.0.2, HyperFrames 0.9.45, mlx-whisper 0.4.3, Node.js 22.22, Python 3.13.18, remotion-motion-graphics at commit 1dcbe5e.

- **FFmpeg (Homebrew build)** has no `drawtext`, `subtitles` or `ass` filters. All text goes through HyperFrames.
- **HyperFrames transcription.** `hyperframes transcribe` needs whisper-cpp, which is not installed, and its default model (`small.en`) translates non-English speech into English. Use this skill's `transcribe.py` instead; its `words.json` is already in the flat `id/text/start/end` shape HyperFrames compositions consume.
- **HyperFrames inside the plugin** runs through its launcher, not bare `npx hyperframes`: `node "<PLUGIN_ROOT>/skills/hyperframes/scripts/plugin-cli.mjs" <command>`. Wherever this skill writes `hyperframes <command>`, use the launcher form.
- **HyperFrames `init --video`** defaults the canvas to 1080 on the short side. A 4K source needs `--resolution landscape-4k` (or the matching portrait preset).
- **HyperFrames telemetry.** The CLI and its skills send usage telemetry to HeyGen. `hyperframes telemetry disable` (or `DO_NOT_TRACK=1`) turns it off; respect whichever the person has chosen.
- **Whisper** runs as `mlx_whisper` (Apple Silicon). Models are fetched from Hugging Face on first use: `mlx-community/whisper-large-v3-mlx` for real work, `mlx-community/whisper-tiny` for the smoke test.
- **Whisper and the script.** Passing the script's text as Whisper's initial prompt makes it skip the speech (it heard 3 of 45 words in testing). `transcribe.py` therefore never does this; `--terms` takes only a short list of names.
- **Bangla word timing** had not yet been tested on real footage when this was written; the English smoke test passed. Treat the first Bangla run as the test and record what you find here.
