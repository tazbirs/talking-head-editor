# Tool notes

Things learned about the installed tools, newest first. Add an entry whenever a release changes a command, flag or behaviour this skill relies on (see `updates.md`), and correct the affected file at the same time.

## 2026-11-14 - first narrated explainer with a natural Bangla voice

- ElevenLabs, voice "Ashwat" (male, Bengali), on a Starter plan: 47 passages, 563 words, 4 min 35 s, 136 words a minute. The render passed `qc.py --voice` with the narration at +0 ms at both ends, -13.1 LUFS.
- **Model choice matters per voice.** Ashwat is verified for Bangla on the `eleven_v4` family and for Hindi on the older models, so the same voice id is a Hindi voice on Multilingual v2 and a Bangla voice on v4. `voice.py` now reads the voice's `verified_languages` and picks a verified model for the narration's language (`eleven_v4` here). A first attempt on `eleven_v3` was stopped part-way.
- **Verification that worked:** Whisper large-v3, left to detect the language itself, returned Bengali; against the narration it heard 559 of 563 words with a match rate of 0.77. Nearly all the misses were English terms spelled in Bangla script (এআই, জুম, স্কিল), which Whisper writes in Latin letters.
- **First measure of Bangla alignment on natural speech:** timing the same audio by transcription (`transcribe.py --by-line`) instead of using the exact per-passage timings gave passage starts with a median error of 0.03 s, 32 of 47 within 0.3 s, 90% within 1.4 s, worst 2.6 s. Good enough to edit to, and worth a look at the few lines it reports as unanchored. On the synthetic macOS voice, which Whisper half-skipped, the same method was off by up to 19 s even after rejecting misplaced matches: when `match_rate` is under about 0.6, do not trust the timings.
- Whisper large-v3 took over ten minutes for this 4.5-minute file while a render was running. Do not run them together.

## 2026-11-14 - voices

- **English, Kokoro (local):** works. Male (`am_adam`) and female (`af_heart`) samples transcribed back at 100% and 98%. At the default speed it reads at about 215 words a minute; `--rate 0.9` gives about 200. HyperFrames' `tts` needs a Python with `kokoro-onnx`; `voice.py` makes one with uv and points `HYPERFRAMES_PYTHON` at it.
- **Bangla, macOS `say` (Piya):** the only local Bangla voice: female, India accent, synthetic. Whisper large-v3 recognised only 40% of a 563-word narration read by it (279 words heard), so it could not be verified. Treat it as a timing draft, never as a deliverable.
- **Bangla, ElevenLabs:** first real calls on 2026-11-14. `--list --engine elevenlabs` worked and showed four Bangla-capable models: `eleven_v3`, `eleven_v3_conversational`, `eleven_v4` and `eleven_v4_turbo`. The model is now chosen per voice from its verified languages (see the entry above), with `eleven_v3` only as the fallback for Bangla when a voice has no verification. Multilingual v2 and Flash v2.5 do not speak Bengali. Voices carry `language: bn` and a gender label, so a Bengali voice can be confirmed from the listing.
- **ElevenLabs free plan and the API:** a Voice Library voice cannot be used through the API on the free plan (`HTTP 402 Free users cannot use library voices via the API`). The free plan only lets the person audition library voices in the web app. To generate with one from this skill they need a paid plan, which publishing needs anyway. No credits are used by the refused call.
- **Bangla, natural male:** exists only online (Microsoft `bn-BD-PradeepNeural`, through Azure with a key, or through the unofficial edge-tts). Both engines are in `voice.py` but neither has been run: the session that wrote them was not allowed to contact the service without the person choosing it. Test before relying on them.
- **Narrated build:** a 4 min 39 s narrated render timed by `voice.py` passed `qc.py --voice` with the narration at +0 ms against the voice file at the start and at the end.
- **Check quirk:** an `<audio class="clip">` that ends before the film counts as a change on screen, and the closing line then fails `line_unread`. End the film with the voice file (`voice.py` leaves 1 s of silence after the last passage).
- **First Bangla transcription with Whisper large-v3** was on that synthetic voice, so it says little about real speech. Real Bangla footage is still untested.

## 2026-11-14 - first full explainer (2 min 29 s, Bangla, 11 scenes)

- Made end to end from a script: 47 on-screen lines, 11 sub-compositions, a real page capture, 20 bundled sound effects. `check` clean, render 65 s on an M2, `qc.py` pass.
- **Pacing.** HyperFrames' `line_unread` check counts reading time only while a line is fully on screen, and counts hyphenated names per part. `pace.py` now adds `--transition` (0.45 s) for the entrance and exit and has a `--min` hold (2.3 s). Text that appears inside a panel late in a line trips the same check: bring it in within about 0.8 s of the line.
- **Sound without sign-in.** `media-use resolve --type sfx --intent "..."` returns HyperFrames' bundled effects (whoosh-short, whoosh-cinematic, pop, key-press, impact-bass, click, riser and others) with no account. Two different intents can return the same file, so check `library_key`. Music and generated voices need the HeyGen sign-in; without it the video has effects only.
- **Placing a sound.** `hyperframes audio <file> --json` gives `moments.peak`; start the clip at `event + 1/30 - peak`. The bass impact is loud (true peak -0.4 dB): `data-volume="0.35"`. An effects-only track measures around -19 LUFS, which `qc.py` reports as a warning; that is expected with no voice or music.
- **Audio clips** go in the root: `<audio id class="clip" src data-start data-duration data-track-index data-volume>`, one track per kind of sound so they never overlap.
- **Exits.** A `fromTo` used as an exit needs `immediateRender: false`, or its start state is applied at build time and the element shows before its entrance.
- **Real page capture.** `hyperframes capture <url> --skip-vision --max-screenshots 3` gave a clean 1920x1080 screenshot of a public GitHub page in about a minute.
- Still untried: a narrated explainer with a real recording, a script written from a topic.

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
