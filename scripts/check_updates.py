#!/usr/bin/env python3
"""Keep the video-editing tools current. Stable releases only.

usage: check_updates.py                     check (at most once a day) and say what to do
       check_updates.py --force             check now, ignoring the daily cache
       check_updates.py --apply             install significant updates, then run the smoke test
       check_updates.py --stage-remotion    download the new Remotion skill for review
       check_updates.py --apply-remotion <commit>   install a reviewed Remotion skill

Prints JSON. Never raises on a network failure: a tool that cannot be checked is listed
under "errors" and left as it is.
"""
import difflib
import json
import os
import re
import shutil
import sys
import time
import urllib.request

from common import APPLE_SILICON, CACHE_DIR, HOME, SKILL_DIR, SYSTEM, run, version_tuple, which

STATE = os.path.join(CACHE_DIR, "update-check.json")
HISTORY = os.path.join(CACHE_DIR, "update-history.jsonl")
POLICY = os.path.join(SKILL_DIR, "scripts", "update-policy.json")
DAY = 24 * 3600

BREW = {"ffmpeg": "ffmpeg", "node": "node@22", "python": "python@3.13", "uv": "uv"}
RUNTIME_LATEST = {"node": "node", "python": "python"}   # unversioned formulae = newest major line

# System package managers other than Homebrew need administrator rights, and on Arch a
# single-package upgrade is unsupported. So on those systems this script only reports a new
# version and the command for the person to run; it never runs sudo or accepts a prompt.
# Each tool lists the package names to try, first installed one wins.
SYSTEM_PACKAGES = {
    "apt": {"ffmpeg": ["ffmpeg"], "node": ["nodejs"], "python": ["python3"], "uv": []},
    "pacman": {"ffmpeg": ["ffmpeg"], "node": ["nodejs-lts-jod", "nodejs"], "python": ["python"], "uv": ["uv"]},
    "dnf": {"ffmpeg": ["ffmpeg", "ffmpeg-free"], "node": ["nodejs22", "nodejs"], "python": ["python3"], "uv": ["uv"]},
    "winget": {"ffmpeg": ["Gyan.FFmpeg"], "node": ["OpenJS.NodeJS.22", "OpenJS.NodeJS.LTS", "OpenJS.NodeJS"],
               "python": ["Python.Python.3.13", "Python.Python.3.12"], "uv": ["astral-sh.uv"]},
}
UPGRADE_COMMAND = {
    "apt": "sudo apt update && sudo apt install --only-upgrade {pkg}",
    "pacman": "sudo pacman -Syu",          # full upgrade: Arch does not support upgrading one package alone
    "dnf": "sudo dnf upgrade {pkg}",
    "winget": "winget upgrade --id {pkg} --exact",
}
BINARY_VERSION = {"ffmpeg": ["ffmpeg", "-version"], "node": ["node", "--version"],
                  "python": [sys.executable, "--version"], "uv": ["uv", "--version"]}
MIN_NODE = 22
WHISPER_TOOL = "mlx-whisper" if APPLE_SILICON else "whisper-ctranslate2"
PLUGIN = "hyperframes@hyperframes"
REMOTION_DIR = os.path.join(HOME, ".claude", "skills", "remotion-motion-graphics")
REMOTION_REPO = "https://github.com/haidrrrry/claude-remotion-skill.git"
REMOTION_SUBDIR = "remotion-motion-graphics"
STAGED = os.path.join(CACHE_DIR, "remotion-staged")

PRERELEASE = re.compile(r"(alpha|beta|rc|dev|nightly|canary|next|pre|snapshot|a\d|b\d)", re.I)


def is_stable(version):
    """True for a plain release number: no pre-release or nightly marker."""
    if not version or not version_tuple(version):
        return False
    rest = re.sub(r"^\D*\d+(\.\d+)*", "", version.strip())
    rest = re.sub(r"^_\d+$", "", rest)            # Homebrew revision such as 9.0.2_1
    rest = re.sub(r"^\.post\d+$", "", rest)       # PyPI post-release
    return not rest and not PRERELEASE.search(version)


def bump(installed, latest):
    """none | patch | minor | major, comparing two version strings."""
    a, b = version_tuple(installed), version_tuple(latest)
    if not a or not b or b <= a:
        return "none"
    if b[0] != a[0]:
        return "major"
    if b[1] != a[1]:
        return "major" if a[0] == 0 else "minor"   # for 0.x tools the minor number is the breaking one
    return "patch"


def policy():
    try:
        with open(POLICY, encoding="utf-8") as f:
            level = json.load(f).get("auto_update", "minor")
    except (OSError, ValueError):
        level = "minor"
    return level if level in ("patch", "minor", "major") else "minor"


def significant(level, threshold):
    order = {"none": 0, "patch": 1, "minor": 2, "major": 3}
    return order[level] >= order[threshold]


def claude_bin():
    return which("claude") or os.path.join(HOME, ".local", "bin", "claude")


# ---- where versions come from -------------------------------------------------------------

def package_manager():
    """brew | apt | pacman | dnf | winget | None, for the system this is running on."""
    if SYSTEM == "Darwin":
        return "brew" if which("brew") else None
    if SYSTEM == "Windows":
        return "winget" if which("winget") else None
    for name, probe_bin in (("apt", "apt-cache"), ("pacman", "pacman"), ("dnf", "dnf"), ("brew", "brew")):
        if which(probe_bin):
            return name
    return None


def binary_version(tool):
    code, out, err = run(BINARY_VERSION[tool], timeout=30)
    text = (out or err).strip().splitlines()[0] if code == 0 and (out or err).strip() else ""
    v = version_tuple(text)
    return ".".join(str(n) for n in v) if v else None


def candidate_version(manager, pkg):
    """The newest version the system's package manager offers for pkg, or None."""
    if manager == "apt":
        _, out, _ = run(["apt-cache", "policy", pkg], timeout=60)
        m = re.search(r"Candidate:\s*(\S+)", out)
        return m.group(1) if m and m.group(1) != "(none)" else None
    if manager == "pacman":
        code, out, _ = run(["pacman", "-Si", pkg], timeout=60)
        m = re.search(r"^Version\s*:\s*(\S+)", out, re.M)
        return m.group(1) if code == 0 and m else None
    if manager == "dnf":
        code, out, _ = run(["dnf", "-q", "repoquery", "--latest-limit=1", "--queryformat", "%{version}\n", pkg],
                           timeout=120)
        lines = [ln.strip() for ln in out.splitlines() if version_tuple(ln)]
        return lines[-1] if code == 0 and lines else None
    if manager == "winget":
        code, out, _ = run(["winget", "show", "--id", pkg, "--exact", "--disable-interactivity"], timeout=120)
        m = re.search(r"^Version:\s*(\S+)", out, re.M)
        return m.group(1) if code == 0 and m else None
    return None


def is_installed(manager, pkg):
    if manager == "apt":
        _, out, _ = run(["apt-cache", "policy", pkg], timeout=60)
        m = re.search(r"Installed:\s*(\S+)", out)
        return bool(m and m.group(1) != "(none)")
    if manager == "pacman":
        return run(["pacman", "-Q", pkg], timeout=30)[0] == 0
    if manager == "dnf":
        return run(["rpm", "-q", pkg], timeout=30)[0] == 0
    if manager == "winget":
        return run(["winget", "list", "--id", pkg, "--exact", "--disable-interactivity"], timeout=120)[0] == 0
    return False


def manual_versions(manager, errors):
    """Versions on systems where this script may not upgrade packages itself."""
    found = {}
    for tool in ("ffmpeg", "node", "python", "uv"):
        installed = binary_version(tool)
        if installed is None:
            errors.append("%s is not installed or not on PATH." % tool)
            continue
        entry = {"installed": installed, "latest": None, "via": "manual", "distro_channel": True}
        candidates = SYSTEM_PACKAGES.get(manager, {}).get(tool, [])
        pkg = next((p for p in candidates if is_installed(manager, p)), None)
        if pkg:
            entry["latest"] = candidate_version(manager, pkg)
            entry["package"] = pkg
            entry["command"] = UPGRADE_COMMAND[manager].format(pkg=pkg)
        elif tool == "uv":
            entry["command"] = "uv self update"      # installed with uv's own installer
            entry["latest"] = pypi_latest("uv", errors)
        else:
            entry["note"] = ("installed outside %s, so its newest version is not known here"
                             % (manager or "a known package manager"))
        found[tool] = entry
    return found


def system_versions(errors):
    manager = package_manager()
    if manager == "brew":
        return brew_versions(errors), manager
    if manager is None:
        errors.append("No supported package manager found (Homebrew, apt, pacman, dnf, winget): "
                      "FFmpeg, Node.js and Python versions are reported but not compared.")
    return manual_versions(manager, errors), manager


def pypi_latest(package, errors):
    """Newest stable, non-yanked release of a PyPI package, or None."""
    try:
        with urllib.request.urlopen("https://pypi.org/pypi/%s/json" % package, timeout=20) as r:
            releases = json.load(r).get("releases", {})
    except Exception as e:                      # offline, DNS, rate limit: not fatal
        errors.append("PyPI could not be reached for %s: %s" % (package, e))
        return None
    stable = [v for v, files in releases.items()
              if is_stable(v) and files and not all(f.get("yanked") for f in files)]
    return max(stable, key=version_tuple) if stable else None


def brew_versions(errors):
    found = {}
    run(["brew", "update", "--quiet"], timeout=180)   # refresh formula data; failure just means stale data
    names = list(BREW.values()) + list(RUNTIME_LATEST.values())
    code, out, err = run(["brew", "info", "--json=v2"] + names, timeout=120)
    if code != 0:
        errors.append("brew info failed: " + err.strip()[-200:])
        return found
    by_name = {f["name"]: f for f in json.loads(out).get("formulae", [])}
    for tool, formula in BREW.items():
        f = by_name.get(formula)
        if not f:
            continue
        installed = f["installed"][-1]["version"] if f.get("installed") else None
        found[tool] = {"installed": installed, "latest": f["versions"].get("stable"), "via": "brew:" + formula}
    for tool, formula in RUNTIME_LATEST.items():
        f = by_name.get(formula)
        if f and tool in found:
            found[tool]["newest_line"] = f["versions"].get("stable")
    return found


def hyperframes_versions(errors):
    installed = None
    code, out, err = run([claude_bin(), "plugin", "list", "--json"], timeout=60)
    if code == 0:
        try:
            for p in json.loads(out):
                if p.get("id") == PLUGIN:
                    installed = p.get("version")
        except ValueError:
            pass
    if installed is None:
        errors.append("The HyperFrames plugin was not found in `claude plugin list`.")
    code, out, err = run(["npm", "view", "hyperframes", "dist-tags.latest"], timeout=60)
    latest = out.strip() if code == 0 else None
    if latest is None:
        errors.append("npm could not be reached for HyperFrames: " + err.strip()[-120:])
    return {"installed": installed, "latest": latest, "via": "claude plugin"}


def whisper_versions(errors):
    installed = None
    _, out, _ = run(["uv", "tool", "list"], timeout=60)
    m = re.search(r"^%s v(\S+)" % re.escape(WHISPER_TOOL), out, re.M)
    if m:
        installed = m.group(1)
    else:
        errors.append("%s is not installed as a uv tool (uv tool install --python 3.12 %s)."
                      % (WHISPER_TOOL, WHISPER_TOOL))
    return {"installed": installed, "latest": pypi_latest(WHISPER_TOOL, errors), "via": "uv tool"}


def remotion_state(errors):
    installed = None
    try:
        with open(os.path.join(REMOTION_DIR, ".source.json"), encoding="utf-8") as f:
            installed = json.load(f).get("commit")
    except (OSError, ValueError):
        errors.append("The Remotion skill has no .source.json: its installed commit is unknown.")
    code, out, err = run(["git", "ls-remote", REMOTION_REPO, "HEAD"], timeout=60)
    latest = out.split()[0] if code == 0 and out.strip() else None
    if latest is None:
        errors.append("GitHub could not be reached for the Remotion skill.")
    return {"installed": installed, "latest": latest, "via": "git (no releases; reviewed by hand)"}


# ---- check --------------------------------------------------------------------------------

def check():
    errors, threshold = [], policy()
    tools, manager = system_versions(errors)
    tools["hyperframes"] = hyperframes_versions(errors)
    tools[WHISPER_TOOL] = whisper_versions(errors)
    to_update, manual, patches, notes = [], [], [], []
    node = version_tuple(tools.get("node", {}).get("installed"))
    if node and node[0] < MIN_NODE:
        errors.append("Node.js %s is too old: HyperFrames needs %d or newer." % (tools["node"]["installed"], MIN_NODE))
    for name, t in tools.items():
        latest = t.get("latest")
        # A distribution's own repository is its stable channel, whatever its version strings look like.
        if latest and not t.get("distro_channel") and not is_stable(latest):
            errors.append("%s: newest listed version %s is not a stable release; ignored." % (name, latest))
            t["level"] = "none"
            continue
        t["level"] = bump(t.get("installed"), latest) if t.get("installed") else "none"
        if t["level"] == "none":
            continue
        if not significant(t["level"], threshold):
            patches.append(name)
        elif t["via"] == "manual":
            manual.append({"tool": name, "from": t["installed"], "to": latest, "level": t["level"],
                           "command": t.get("command")})
        else:
            to_update.append(name)
    # Node and Python stay on their current line; a newer line is only reported.
    for name in ("node", "python"):
        t = tools.get(name, {})
        line = t.get("newest_line")
        a, b = version_tuple(t.get("installed")), version_tuple(line)
        width = 2 if name == "python" else 1      # Python's line is major.minor
        if a and b and b[:width] > a[:width]:
            notes.append("%s %s exists; this setup stays on %s unless a tool requires the newer line."
                         % (name, line, t["installed"]))
    remotion = remotion_state(errors)
    review = bool(remotion["installed"] and remotion["latest"] and remotion["installed"] != remotion["latest"])
    tools["remotion-skill"] = remotion
    return {
        "checked_at": int(time.time()),
        "system": SYSTEM,
        "package_manager": manager,
        "channel": "stable releases only",
        "auto_update": threshold,
        "tools": tools,
        "to_update": to_update,
        "manual_updates": manual,
        "available_patches": patches,
        "review_remotion": review,
        "runtime_notes": notes,
        "errors": errors,
        "action": "apply" if to_update else ("review_remotion" if review else "none"),
    }


def cached_check(force):
    if not force:
        try:
            with open(STATE, encoding="utf-8") as f:
                state = json.load(f)
            if time.time() - state.get("checked_at", 0) < DAY:
                state["from_cache"] = True
                return state
        except (OSError, ValueError):
            pass
    state = check()
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
    state["from_cache"] = False
    return state


# ---- apply --------------------------------------------------------------------------------

def update_tool(name, tool):
    if tool["via"].startswith("brew:"):
        return run(["brew", "upgrade", tool["via"].split(":", 1)[1]], timeout=3000)
    if name == "hyperframes":
        code, out, err = run([claude_bin(), "plugin", "marketplace", "update", "hyperframes"], timeout=600)
        if code != 0:
            return code, out, err
        return run([claude_bin(), "plugin", "update", PLUGIN], timeout=600)
    if name == WHISPER_TOOL:
        return run(["uv", "tool", "upgrade", WHISPER_TOOL], timeout=1800)
    return 1, "", "no updater for %s" % name


def broken_formulae():
    """Homebrew packages whose libraries no longer resolve.

    Upgrading one package can upgrade a shared library under another package that was not
    part of the update (seen on 2026-11-14: upgrading node@22 moved simdjson and broke a
    separately installed `node`).
    """
    if package_manager() != "brew":
        return []
    _, out, err = run(["brew", "linkage", "--test"], timeout=600)
    broken, current = [], None
    for line in (out + "\n" + err).splitlines():
        m = re.match(r"==> Checking (\S+) linkage", line)
        if m:
            current = m.group(1)
        elif current and re.match(r"\s*(Broken dependencies|Missing libraries|Broken dependents)", line):
            if current not in broken:
                broken.append(current)
    return broken


def repair_brew():
    """Reinstall or upgrade whatever an update left broken. Returns (repaired, still_broken)."""
    broken = broken_formulae()
    if not broken:
        return [], []
    for formula in broken:
        code, _, _ = run(["brew", "upgrade", formula], timeout=3000)
        if code != 0:
            run(["brew", "reinstall", formula], timeout=3000)
    still = broken_formulae()
    return [f for f in broken if f not in still], still


def apply():
    before = check()
    updated, failed = [], []
    for name in before["to_update"]:
        tool = before["tools"][name]
        code, out, err = update_tool(name, tool)
        if code == 0:
            updated.append({"tool": name, "from": tool["installed"], "to": tool["latest"], "level": tool["level"]})
        else:
            failed.append({"tool": name, "from": tool["installed"], "wanted": tool["latest"],
                           "error": (err or out).strip()[-300:]})
    repaired, still_broken = repair_brew()
    code, out, err = run([sys.executable, os.path.join(SKILL_DIR, "scripts", "smoke_test.py")], timeout=1800)
    try:
        smoke = json.loads(out)
    except ValueError:
        smoke = {"ok": False, "detail": (err or out).strip()[-300:]}
    after = check()
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(after, f, indent=1)
    result = {
        "updated": updated,
        "failed": failed,
        "significant": [u["tool"] for u in updated],
        "other_packages_repaired": repaired,
        "other_packages_still_broken": still_broken,
        "manual_updates": after["manual_updates"],
        "smoke": smoke,
        "review_remotion": after["review_remotion"],
        "restart_needed": any(u["tool"] == "hyperframes" for u in updated),
        "next": "Look at smoke.frame, then follow references/updates.md (After --apply).",
    }
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": int(time.time()), "updated": updated, "failed": failed,
                            "smoke_ok": bool(smoke.get("ok"))}) + "\n")
    return result


# ---- the Remotion skill: stage, review, install --------------------------------------------

def tree_diff(old_dir, new_dir, skip=(".source.json",)):
    """A unified diff of two folders, without needing a `diff` program (Windows has none)."""
    def files(root):
        out = {}
        for base, _, names in os.walk(root):
            for n in names:
                if n not in skip:
                    full = os.path.join(base, n)
                    out[os.path.relpath(full, root).replace(os.sep, "/")] = full
        return out

    def lines(path):
        if not path:
            return []
        try:
            with open(path, encoding="utf-8") as f:
                return f.read().splitlines(keepends=True)
        except (UnicodeDecodeError, OSError):
            return None                                   # binary or unreadable

    old, new, chunks = files(old_dir), files(new_dir), []
    for rel in sorted(set(old) | set(new)):
        a, b = lines(old.get(rel)), lines(new.get(rel))
        if a is None or b is None:
            with_change = not (old.get(rel) and new.get(rel)) or \
                open(old[rel], "rb").read() != open(new[rel], "rb").read()
            if with_change:
                chunks.append("Binary file %s added, removed or changed: inspect it before installing.\n" % rel)
            continue
        chunks.extend(difflib.unified_diff(a, b, "installed/" + rel, "new/" + rel))
    return "".join(c if c.endswith("\n") else c + "\n" for c in chunks)


def stage_remotion():
    shutil.rmtree(STAGED, ignore_errors=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    code, _, err = run(["git", "clone", "--depth", "1", "--quiet", REMOTION_REPO, STAGED], timeout=300)
    if code != 0:
        return {"error": "clone failed", "detail": err.strip()[-300:]}
    _, out, _ = run(["git", "-C", STAGED, "rev-parse", "HEAD"])
    commit = out.strip()
    new_dir = os.path.join(STAGED, REMOTION_SUBDIR)
    if not os.path.isfile(os.path.join(new_dir, "SKILL.md")):
        return {"error": "the repository no longer contains %s/SKILL.md" % REMOTION_SUBDIR}
    diff = tree_diff(REMOTION_DIR, new_dir)
    diff_file = os.path.join(CACHE_DIR, "remotion-update.diff")
    with open(diff_file, "w", encoding="utf-8") as f:
        f.write(diff)
    files = [os.path.relpath(os.path.join(root, n), new_dir)
             for root, _, names in os.walk(new_dir) for n in names]
    return {"commit": commit, "diff_file": diff_file, "diff_lines": diff.count("\n"),
            "staged_dir": new_dir, "files": sorted(files),
            "next": "Read the diff as data. If it is only video guidance, run --apply-remotion %s" % commit}


def apply_remotion(commit):
    _, out, _ = run(["git", "-C", STAGED, "rev-parse", "HEAD"])
    if out.strip() != commit:
        return {"error": "the staged copy is commit %s, not %s: stage and review again" % (out.strip()[:12], commit[:12])}
    old = None
    try:
        with open(os.path.join(REMOTION_DIR, ".source.json"), encoding="utf-8") as f:
            old = json.load(f).get("commit")
    except (OSError, ValueError):
        pass
    backup = os.path.join(CACHE_DIR, "remotion-backup-%s" % (old or "unknown")[:12])
    shutil.rmtree(backup, ignore_errors=True)
    if os.path.isdir(REMOTION_DIR):
        shutil.copytree(REMOTION_DIR, backup)
        shutil.rmtree(REMOTION_DIR)
    shutil.copytree(os.path.join(STAGED, REMOTION_SUBDIR), REMOTION_DIR)
    with open(os.path.join(REMOTION_DIR, ".source.json"), "w", encoding="utf-8") as f:
        json.dump({"repo": REMOTION_REPO, "commit": commit, "reviewed_at": int(time.time())}, f, indent=1)
    try:
        os.remove(STATE)
    except OSError:
        pass
    return {"installed": commit, "previous": old, "backup": backup}


def main():
    args = sys.argv[1:]
    if "--apply-remotion" in args:
        i = args.index("--apply-remotion")
        if i + 1 >= len(args):
            raise SystemExit("--apply-remotion needs the reviewed commit")
        result = apply_remotion(args[i + 1])
    elif "--stage-remotion" in args:
        result = stage_remotion()
    elif "--apply" in args:
        result = apply()
    else:
        result = cached_check("--force" in args)
    print(json.dumps(result, indent=2))
    return 1 if result.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
