# The edit plan

The plan is the edit, written down before any HTML. `qc.py` also reads it to pick the frames it shows you, so keep it accurate when the build changes.

## Format

`edit-plan.json`:

```json
{
  "source": {"file": "talk.mp4", "width": 1920, "height": 1080, "fps": "30/1", "duration": 412.6},
  "language": "bn",
  "face_box": {"x": 0.38, "y": 0.12, "w": 0.24, "h": 0.36},
  "look": {"palette": ["#0B1B3A", "#FFD23F", "#FFFFFF"], "bangla_font": "Hind Siliguri", "latin_font": "Montserrat"},
  "chapters": [{"id": "hook", "start": 0.0, "end": 21.4, "title": "The promise"}],
  "beats": [
    {
      "id": "b012",
      "start": 48.20, "end": 53.05,
      "text": "এই টুলটি সম্পূর্ণ ফ্রি",
      "emotion": "excitement",
      "layout": "reverse-split",
      "camera": {"move": "punch-in", "scale": 1.12, "over": 0.35},
      "graphic": {"kind": "big-word", "content": "FREE", "anchor_word": "w231", "source": "type"},
      "sfx": [{"sound": "impact-soft", "at": 49.02, "cause": "FREE lands"}],
      "why": "The key claim of the video; first time it is said."
    }
  ]
}
```

- `start` / `end` come from `sentences.json`. `anchor_word` is a `words.json` id: the graphic lands on that word.
- `graphic.source` says where the picture comes from: `type` (typography), `diagram` (drawn, abstract), `capture` (a real page, with its URL), `logo` (resolved through media-use), `person` (a file the person supplied). Nothing else is allowed, which is what stops invented interfaces.
- `why` is one line. If you cannot write it, the beat does not need a treatment: set `layout` to `full`, `graphic` to `null`.

## Layouts

| Layout | Picture | Use for |
| --- | --- | --- |
| `full` | Speaker fills the frame, subtle camera life | Normal explanation, personal moments |
| `split` | Speaker left, graphics right | A list, a process, a demonstration |
| `reverse-split` | Speaker right, text or graphics left | A key statement, a number |
| `pip` | Speaker small in a corner, large visual | Screenshots, a site tour, a long demo |
| `graphics` | Full-screen graphic, voice continues | A reveal, a comparison, a chapter title |
| `closeup` | Tight on the face | The one thing they must not miss |

Video rectangles for split and picture-in-picture are in the HyperFrames skill's `references/overlays.md`; use those numbers.

- Choose the side from `face_box`: the speaker moves toward the side they already lean to, and graphics take the empty side. In a split, the speaker's rectangle must contain the whole face and shoulders; if the source framing cannot give that, use `pip` instead of cropping.
- A layout holds for at least about 4 s and rarely more than 20 s. Change it on a sentence boundary, during a breath, never mid-word.
- Re-frame the speaker over 0.5-0.7 s, and only in a gap between cards.
- Do not cycle the layouts in a fixed order; the content picks the layout.

## Camera

| Move | Amount | Use |
| --- | --- | --- |
| Slow push-in | 1.00 to 1.06 over the whole sentence | Building a point, suspense |
| Slow pull-back | reverse of the above | Releasing after a point, a new topic |
| Punch-in | cut or 0.2-0.35 s to 1.10-1.20 | A surprise, a key word |
| Drift | 1-2% position change over 6-10 s | Keeping a long `full` shot alive |

- Ceiling: the footage may be scaled to about 1.25 when the canvas equals the source resolution. A 4K source on a 1080p canvas can go to 2.0. Past the ceiling the face goes soft.
- After any scale or move, the whole `face_box` plus a margin of 8% of the frame stays inside the picture. Check this with a snapshot, not by arithmetic alone.
- Scale uniformly. Never change the aspect of the footage.
- Never use the same move on two beats in a row, and no more than about one punch-in per 20 s. A punch-in on every sentence is the most common sign of an automated edit.

## Emotion to treatment

Read each sentence for what the speaker is doing with it, then pick from the row. Intensity follows the speech: a calm speaker saying "free" gets clean type, not an explosion.

| The sentence is | Camera | Graphic | Sound |
| --- | --- | --- | --- |
| Excitement | Punch-in or quick push | Large type, energetic entrance | Whoosh into soft impact |
| Surprise, a reveal | Hold still, then punch-in on the word | Reveal animation, one big element | Riser into impact, once per video for the main reveal |
| Important explanation | Slow push-in | Diagram, highlighted terms, steps arriving one by one | Soft ticks or pops on arrivals |
| Suspense | Very slow push-in | Little or nothing | A low riser, or silence |
| Confidence, a claim | Steady, `reverse-split` | Clean bold statement | One soft impact |
| Normal explanation | Drift only | Nothing, or a small keyword | Nothing |

## What triggers a graphic

| The speaker | Show |
| --- | --- |
| Names an AI tool or product | Its real logo and name |
| Says free / unlimited / no watermark | That word, large, in English or Bangla as spoken |
| Gives a number, price, credits | A counter that runs to the number |
| Talks about money or income | A number or simple chart with a currency mark; no clip-art |
| Explains a process | Steps appearing in order, each on its own sentence |
| Introduces a website | A real capture of the page, with the relevant part highlighted |
| Mentions a feature | A highlight on the real interface if you have a capture; otherwise a labelled diagram |
| Compares two things | A two-column before / after |

## Density

Starting points; the content overrides them.

- A visual change (layout, camera or graphic) roughly every 4-8 s in the first 30 s, where viewers decide to stay; every 6-12 s after that.
- At most one focal graphic on screen at a time. If two things compete, the second waits.
- Leave some sentences completely clean. Contrast is what makes the treated moments land.
- The first 5 s shows the video's promise in type, on the words that say it.
- Clamp every end time, and the root `data-duration`, to the footage's ffprobe duration: a transcript's last word can run past the file and the render then ends in black.
