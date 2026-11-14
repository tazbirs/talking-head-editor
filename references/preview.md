# Show it in the editor before exporting

The person asked for this: before the final export, the video opens in the HyperFrames editor (Studio) in their browser, so they can watch it and change things by hand. A change costs seconds there and a full re-render afterwards, so this is the one planned stop of the whole job. It comes after your own checks, so what they see is already clean.

## Open it

When `check` passes and the snapshots are clean:

```bash
python3 "$SKILL_DIR/scripts/preview.py" <dir>
```

It starts Studio in the background, opens it in the person's default browser, confirms the page answers, and remembers the contents of every source file so that hand changes can be found later. Use the `studio_url` it prints: the bare `index.html` path is not the editor. If you are showing the page in an in-app browser pane yourself, add `--no-open` and open that URL there.

Do not start Studio with `npm run dev` or a backgrounded shell command: that server dies with the command that started it.

## What to tell the person

Keep it to a few lines, then stop and wait:

- the link, and that the video is ready to watch there from start to end;
- what they can do: play it, click anything on the picture to change its text, font, size, colour or position, drag a clip on the timeline to move or trim it, undo with the arrow buttons;
- two ways to go on: say **render** when it looks right, or tell you what to change. They can click an element in the editor and say "make this bigger": you can read what they selected (below);
- that the editor's own Export button works, but exporting through you also runs the quality check (sync, loudness, a look at every scene), so "render" is the better route.

Do not list your creative decisions here; those go in the delivery note.

## When not to stop

- The person said in this conversation that they do not want the preview ("just give me the file", "no preview"). Render, and put the preview command in the delivery note.
- Nobody is there to look: a scheduled or unattended run, or a machine with no desktop browser (a server over SSH, a cloud session). Render and say the preview was skipped and why.
- They have already seen this video in the editor and asked for a fix. Make the fix; Studio reloads by itself and they see it. Ask "render?" once, not a new walkthrough.
- Studio will not start (port in use, browser missing). Try `--port <another>` once; if it still fails, render and say so. A failed preview never blocks a video.

## While it is open

- **The HTML files are now the source of truth.** Studio writes the person's changes straight into `index.html` and the files in `compositions/`. If you built those files with a generator script (`build.py` or similar), do not run it again: it rewrites the files and erases their work. `preview.py` names such scripts in its `warning`. Make any further change in the HTML itself.
- Studio adds `data-hf-id` attributes and inline `style` values to the elements it touches. Leave them.
- Your own edits to the files show up in the open editor within a second; no restart.
- "This one", "the selected card", "the thing I clicked":

  ```bash
  hyperframes preview --context --json --context-fields selection
  ```

  gives the file, the element (`selection.target.hfId`, else `selector`) and the time on the timeline. If it reports `no-selection`, ask them to click the element and run it again. Do not guess the element from a description when the editor can tell you.

## When they say render

1. `python3 "$SKILL_DIR/scripts/preview.py" <dir> --changes` lists the files changed since the editor opened.
2. If `edited_by_hand` is true: run `hyperframes check --json` again and snapshot the changed scenes. Their choices stand: do not undo a change because you would have done it differently. Repair only what stops the render or is plainly an accident (text pushed off the frame, an element dropped onto the speaker's face), and say exactly what you touched.
3. Moving graphics on the timeline does not move the voice. If they retimed a scene under a narration, say that the words and the picture may no longer meet at that point, and let `qc.py` measure the voice as usual.
4. Render and verify as in the next step.
5. After delivery, `python3 "$SKILL_DIR/scripts/preview.py" <dir> --stop`, unless they are still working in the editor. In the delivery note, name the files that carry their hand changes.

A later re-render of the same project starts from the HTML as it is, never from the generator.
