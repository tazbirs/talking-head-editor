# Platforms

The scripts detect the system themselves. This file is for when something is missing or behaves differently. Installing system packages is the person's step: give them the command, do not run `sudo` or accept an administrator prompt yourself.

## What every system needs

| Tool | Minimum | Check |
| --- | --- | --- |
| FFmpeg with libx264 and AAC | 6 | `ffmpeg -version` |
| Node.js | 22 | `node --version` |
| Python | 3.9 | `python3 --version` (`python --version` on Windows) |
| uv | any | `uv --version` |
| git | any | `git --version` |
| A Whisper engine | | `uv tool list` |
| HyperFrames plugin | | `claude plugin list` |

`python3 scripts/smoke_test.py` proves the whole chain in about a minute and names the stage that fails.

## Whisper engine

| System | Engine | Install |
| --- | --- | --- |
| Mac with Apple Silicon | `mlx-whisper` (uses the Mac's GPU) | `uv tool install --python 3.12 mlx-whisper` |
| Intel Mac, Linux, Windows | `whisper-ctranslate2` (CPU, or NVIDIA GPU) | `uv tool install --python 3.12 whisper-ctranslate2` |

`transcribe.py` picks whichever is installed; both give the same output files.

- With an NVIDIA GPU, `whisper-ctranslate2` uses it when the CUDA libraries (cuBLAS, cuDNN) are present; without them it falls back to the CPU.
- CPU only: large-v3 runs several times slower than real time. For a long video use `--model medium` and tell the person the trade-off (medium is weaker on Bangla).

## macOS

```bash
brew install ffmpeg node@22 python@3.13 uv git
```

Homebrew updates are applied automatically. Two Node installs can coexist (`node@22` and an unversioned `node`); the scripts put Node 22 first.

## Debian and Ubuntu

```bash
sudo apt update && sudo apt install ffmpeg python3 git espeak-ng
```

- **Node.js:** Debian's own package is older than 22 (18 on Debian 12, 20 on Debian 13). Install Node 22 from NodeSource (https://github.com/nodesource/distributions) or with a version manager such as `fnm` or `nvm`.
- **uv:** not in apt. Install it with its official installer (https://docs.astral.sh/uv/getting-started/installation/) or `pipx install uv`.
- `espeak-ng` is only for the smoke test's spoken test clip; without it the Whisper stage is skipped.
- FFmpeg on Debian stable is several versions behind. That is fine: this skill uses nothing newer than FFmpeg 6.

## Arch

```bash
sudo pacman -S ffmpeg nodejs-lts-jod npm python uv git espeak-ng
```

`nodejs-lts-jod` is the Node 22 line; the current `nodejs` package also works. Arch does not support upgrading single packages, so update commands from this skill are always the full `sudo pacman -Syu`.

## Fedora

```bash
sudo dnf install ffmpeg-free nodejs python3 uv git espeak-ng
```

`ffmpeg-free` may lack the H.264 encoder (libx264). If `smoke_test.py` fails at the FFmpeg stage, the person needs the full `ffmpeg` from RPM Fusion.

## Windows

```bash
winget install Gyan.FFmpeg OpenJS.NodeJS.22 Python.Python.3.13 astral-sh.uv Git.Git
```

- Use `python` where this skill writes `python3`.
- Open a new terminal after installing so `PATH` picks the tools up.
- Paths with spaces need quotes. Keep the project on a local drive; network drives make renders very slow.
- The smoke test speaks its test clip through Windows' built-in speech synthesiser, so nothing extra is needed.

## Linux rendering

HyperFrames renders through headless Chrome. On a fresh Linux system:

- `hyperframes browser ensure` downloads the browser; `hyperframes doctor` lists missing system libraries.
- Without a GPU the render summary says `software gpu`: it works, but slowly. Tell the person the expected time for a long video.
- Bengali text does not depend on system fonts: the skill's bundled fonts are loaded with `@font-face`.

## Any other system

With no known package manager the update check still reports installed versions, updates the HyperFrames plugin and Whisper, and says it could not compare the system tools. Everything else works as long as the tools in the first table are on `PATH`.
