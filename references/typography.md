# Typography: Bangla and English

## Fonts

Bundled in this skill's `assets/fonts/` (all SIL Open Font License):

| Family | Files | Use |
| --- | --- | --- |
| Hind Siliguri | `HindSiliguri-Regular/Medium/SemiBold/Bold.ttf` | Default for Bangla: headlines, captions, callouts |
| Noto Sans Bengali | `NotoSansBengali-Variable.ttf` (weight 100-900) | When a heavier weight than Bold is needed (800-900) |
| Noto Serif Bengali | `NotoSerifBengali-Variable.ttf` | A quote or an editorial moment; sparingly |

English display type: one of HyperFrames' bundled families (Montserrat, Poppins, Inter, Outfit, Archivo Black). Pick one Latin family per video and pair it with Hind Siliguri by weight, not by name: bold with bold.

Copy the files you use into the project's `assets/fonts/` and declare them in each composition file that uses them:

```css
@font-face {
  font-family: "Hind Siliguri";
  src: url("assets/fonts/HindSiliguri-Bold.ttf") format("truetype");
  font-weight: 700;
}
.bn { font-family: "Hind Siliguri", "Noto Sans Bengali", sans-serif; }
```

Without the `@font-face`, the family falls back to a system font, lint fails, and Bengali may render in a face that lacks conjuncts.

## Mixed lines

A Bangla sentence with English terms ("এই AI টুলটি সম্পূর্ণ FREE") sets Bangla in the Bangla family and the Latin words in the Latin family. Put the Bangla family first in the stack and let the Latin words fall through only if you want the Bangla font's Latin; for emphasis words, wrap them in a span with the Latin display font. Match x-height by eye: Latin capitals next to Bangla usually need to be about 5-8% smaller to look the same size.

Technical terms stay in English as the speaker says them: FREE, UNLIMITED, AI VIDEO, NO WATERMARK, tool names. Do not translate a product name.

## Bengali shaping: what breaks and how to see it

Bengali is not letter-by-letter. Conjuncts (ক্ষ, ত্র, ম্প), vowel signs that sit before, above or below the consonant (ি, ে, ু, ূ), and reph (র্ক) are formed by the font across several code points.

- **Never split Bengali text into single characters for animation.** Splitting by code point tears conjuncts apart and leaves dotted circles. Animate by word. If a per-letter effect is wanted, split by grapheme cluster with `Intl.Segmenter("bn", {granularity: "grapheme"})`, and still check the frames.
- No `letter-spacing` on Bengali: tracking opens gaps inside conjuncts. Use word spacing and size instead.
- No faux bold or italic: use a real weight file. Bengali has no italic; do not slant it.
- Give lines room: `line-height` 1.35-1.5. Vowel signs above and below collide at Latin line heights.
- Keep text NFC-normalized and exactly as the script has it; do not "fix" spelling.
- Bengali digits (০-৯) when the script uses them, Latin digits when it does not. A counter animates in the same digit system it ends in.

In every snapshot with Bengali text, look for: dotted circles (◌), a visible hasanta (্) where a conjunct should be, a vowel sign floating away from its consonant, boxes. Any of these means the wrong font loaded or the text was split.

## Size and placement

For a 1920x1080 canvas (scale for others):

| Role | Size | Weight |
| --- | --- | --- |
| Big word (FREE, a number) | 160-280 px | 700-900 |
| Headline / key statement | 72-110 px | 700 |
| Supporting line | 40-56 px | 500-600 |
| Caption (word-by-word) | 52-64 px | 600-700 |

- Bengali needs about 10% more size than Latin for the same legibility on a phone.
- At most about six words in a headline; split a longer sentence into the phrase that matters.
- Key text stays inside the 80% title-safe area and never covers the face.
- Over footage, text needs its own contrast: a dark scrim, a solid plate, or a heavy shadow. White type on a bright wall is unreadable.
- One accent colour per video. The highlighted word in a caption takes the accent; the rest stay neutral.
- Keep the same families, sizes and accent through the whole video. Consistency is most of what reads as "professional".

## Text motion

Slide-in, pop, word-by-word highlight, animated underline, scale-up, counters: build them from registry blocks where they exist. Entrances combine two or three properties (opacity with a rise and a slight scale), arrive staggered by 3-6 frames, and exits are faster than entrances. Text holds long enough to read: about 0.3 s per word, at least 1.2 s.
