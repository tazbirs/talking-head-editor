#!/usr/bin/env python3
"""Open the video in the HyperFrames editor (Studio) before it is exported, and find out
afterwards what the person changed there by hand.

  preview.py <project dir>             start Studio, open it in the browser, remember the files
  preview.py <project dir> --no-open   same, without opening a browser window
  preview.py <project dir> --changes   which source files changed since Studio was opened
  preview.py <project dir> --stop      stop Studio (after the render)

Studio edits the same HTML files the video is built from, so "what changed" is a comparison
of file contents before and after. Prints JSON. Standard library only.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

STATE = ".preview-handoff.json"
SOURCE = (".html", ".css", ".js", ".svg")
SKIP_DIRS = {"node_modules", "out", "renders", "snapshots", "voice", "transcript"}


def source_files(project):
    """{relative path: sha1} for every file Studio can edit."""
    found = {}
    for root, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in files:
            if name.lower().endswith(SOURCE):
                path = os.path.join(root, name)
                with open(path, "rb") as f:
                    found[os.path.relpath(path, project).replace(os.sep, "/")] = \
                        hashlib.sha1(f.read()).hexdigest()
    return found


def generators(project):
    """Scripts in the project that write the HTML (build.py and the like)."""
    return sorted(n for n in os.listdir(project)
                  if n.lower().startswith(("build.", "generate.", "make_"))
                  and n.lower().endswith((".py", ".mjs", ".js", ".ts", ".sh")))


def hf(project, *args, timeout=180):
    code, out, err = common.run(common.hyperframes_cmd() + ["preview"] + list(args),
                                timeout=timeout, cwd=project)
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                pass
    return {"ok": False, "error": (err or out).strip()[-600:] or "no output", "code": code}


def reachable(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def start(project, args):
    if not os.path.exists(os.path.join(project, "index.html")):
        return {"ok": False, "error": "no index.html in %s: this is not a HyperFrames project" % project}
    cmd = ["--background", "--json"]
    if args.no_open:
        cmd.append("--no-open")
    if args.port:
        cmd += ["--port", str(args.port)]
    reply = hf(project, *cmd)
    result = reply.get("result") or {}
    url = result.get("studioUrl")
    if not reply.get("ok") or not url:
        return {"ok": False, "error": reply.get("error") or reply, "hint":
                "Run `hyperframes preview --background` in the project to see the full message."}
    ok = False
    for _ in range(10):                     # the server answers a moment after it reports ready
        if reachable(result.get("serverUrl", url)):
            ok = True
            break
        time.sleep(1)
    files = source_files(project)
    with open(os.path.join(project, STATE), "w", encoding="utf-8") as f:
        json.dump({"opened": time.strftime("%Y-%m-%dT%H:%M:%S"), "studio_url": url,
                   "files": files}, f, indent=1)
    out = {"ok": ok, "studio_url": url, "state": result.get("state"), "port": result.get("port"),
           "browser_open_requested": not args.no_open, "files_remembered": len(files)}
    gens = generators(project)
    if gens:
        out["generator_scripts"] = gens
        out["warning"] = ("From now on the HTML files are the source of truth. Running %s again "
                          "rewrites them and erases anything changed in the editor." % ", ".join(gens))
    if not ok:
        out["error"] = "Studio started but %s does not answer" % result.get("serverUrl", url)
    return out


def changes(project):
    path = os.path.join(project, STATE)
    if not os.path.exists(path):
        return {"ok": False, "error": "Studio was not opened with preview.py for this project"}
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    before, now = state["files"], source_files(project)
    out = {"ok": True, "since": state["opened"],
           "changed": sorted(p for p in now if p in before and now[p] != before[p]),
           "added": sorted(p for p in now if p not in before),
           "removed": sorted(p for p in before if p not in now)}
    out["edited_by_hand"] = bool(out["changed"] or out["added"] or out["removed"])
    gens = generators(project)
    if out["edited_by_hand"] and gens:
        out["warning"] = ("Do not run %s again: it would erase these changes. Edit the HTML "
                          "directly from here on." % ", ".join(gens))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--port", type=int)
    ap.add_argument("--changes", action="store_true")
    ap.add_argument("--stop", action="store_true")
    args = ap.parse_args()
    project = os.path.abspath(args.project)
    if not os.path.isdir(project):
        raise SystemExit(json.dumps({"ok": False, "error": "not a folder: %s" % project}))
    if args.changes:
        out = changes(project)
    elif args.stop:
        reply = hf(project, "--stop", "--json")
        out = {"ok": bool(reply.get("ok")), "state": (reply.get("result") or {}).get("state"),
               "detail": None if reply.get("ok") else reply.get("error")}
    else:
        out = start(project, args)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(0 if out.get("ok") else 1)


if __name__ == "__main__":
    main()
