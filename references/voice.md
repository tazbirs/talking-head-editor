# Voice

For a video with no footage of a speaker. (When editing footage, the speaker's own voice is the voice: do not replace it.)

## Always ask first

Before building, ask the person one question, every time, even when they said "no stops":

> Do you want to record the narration yourself, have a generated voice read it, or have no voice?

Ask it once, together with anything else only they can answer. Do not pick for them: the voice is how the video sounds under their name, a generated voice may cost money or send the script to an outside service, and re-timing a finished video to a different voice means rebuilding it.

If they choose a generated voice, tell them in the same breath what is available for the language (table below), which options are free, which need their own key, which send the script off this machine, and which are fit to publish. Then use the one they pick. If they already said which they want, do not ask again.

## The three paths

| Their answer | What you do |
| --- | --- |
| **Their own recording** | Give them the narration as a text file to read. When they hand back the audio: `transcribe.py <audio> --out <dir>/transcript --language bn --script <narration>`. Best result, always fit to publish. |
| **A generated voice** | `voice.py <narration> --out <dir>/voice --engine <engine> --gender male --lines <on-screen lines>`, then verify (below). |
| **No voice** | `pace.py <on-screen lines> --out <dir>/transcript`. Type and sound carry it. |

All three write the same `sentences.json` and `words.json`, so the build does not change.

## Generated voices

`python3 scripts/voice.py --list` prints the engines and voices.

| Engine | Bangla | English | Cost and account | Leaves this machine | Fit to publish |
| --- | --- | --- | --- | --- | --- |
| `kokoro` (HyperFrames, local) | none | natural, male and female | free, no account | no | yes |
| `elevenlabs` (ElevenLabs) | natural and expressive, on the Eleven v3 model only; the accent depends on the voice the person picks | natural, many | the person's own key; 10,000 characters a month free, commercial licence from the Starter plan | yes, to ElevenLabs | yes, on a paid plan |
| `azure` (Microsoft Azure Speech) | natural, male (Pradeep) and female (Nabanita), Bangladesh accent | natural, many | the person's own Azure key; has a free monthly allowance | yes, to Microsoft | yes, licensed |
| `edge` (same Microsoft voices, unofficial tool) | same voices | same voices | free, no account | yes, to Microsoft | unclear: not a licensed route |
| `say` (macOS built-in) | Piya only: female, India accent, synthetic | several | free, macOS only | no | no: Apple licenses system voices for personal, non-commercial use |
| HeyGen voices (`/hyperframes:media-use --type voice`) | check what it offers | yes | the person's HeyGen sign-in; a small free allowance, then paid | yes, to HeyGen | yes |

What follows from the table:

- **English:** `kokoro` is the default. Local, free, natural. It sets itself up on first use (a small Python environment under `~/.cache/talking-head-editor/`).
- **Bangla:** there is no natural Bangla voice that is both local and free. The honest choices are the person's own recording, `elevenlabs` or `azure` with their key, or `edge` if they accept that it is an unofficial route. `say` is a draft voice for checking timing, not for publishing.
- **ElevenLabs:** the person picks the voice by ear in their own account and adds it to their voices; you cannot judge an accent. `voice.py --list --engine elevenlabs` shows their voices and which models can speak Bangla (it should include `eleven_v3`; set `ELEVENLABS_MODEL` if the id has changed). Pass the voice by name or id with `--voice`. The free plan is for trying a voice; tell the person that publishing needs a paid plan.
- Never run an engine that sends the script to an outside service unless the person chose that engine in this conversation. Their key goes in the environment (`ELEVENLABS_API_KEY`, or `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION`) or in a file they create themselves, `~/.config/talking-head-editor/keys.env`, as `NAME=value` lines. Never ask them to paste a key into the chat, never write one to a file yourself, and never print one.
- Do not create an account or a key for the person.
- A voice in the wrong language or accent reading the text is worse than no voice. If nothing suitable exists, say so.

## Writing the narration file

One spoken passage per line, a blank line between scenes, notes in brackets. When the video already has on-screen lines, keep the narration passage for passage with them and pass `--lines`: each passage holds the screen for as long as it takes to say, plus a short pause.

- The narration says more than the screen shows. A voice reading the on-screen line word for word is the mark of an automated video.
- About 10-20 spoken words per passage; around 19 words per scene beat.
- **Write for the ear.** In a Bangla narration, spell English terms in Bangla script the way a Bangla speaker says them (হাইপারফ্রেমস, গিটহাব, স্টেবল ভার্সন), write numbers as words, and expand symbols. A Bangla voice may skip or mangle Latin text. The on-screen lines keep the English spelling.
- Names with an unusual reading need a test: speak one sentence, transcribe it, and adjust the spelling until it comes back right.
- The person's own script is used as they wrote it; only add spoken-form spelling for the voice, and tell them what you changed.

## Verify what you cannot hear

1. Read `voice.py`'s summary. `words_per_minute` is counted on speech only, without the pauses between passages: roughly 110-150 for Bangla and 170-200 for English. Far outside that, change `--rate` (Kokoro reads briskly; `--rate 0.9` is a good start).
2. Transcribe the result against the narration:
   `transcribe.py <dir>/voice/voiceover.wav --out <dir>/voice/check --language bn --script <narration>`
   A `match_rate` above about 0.8 means the words are recognisable. Lower: read which words came back wrong (`words.json`, `how: interp`) and fix their spelling in the narration. If it stays low, the voice itself is the problem: tell the person you could not verify it, and do not present it as finished.
3. After rendering: `qc.py --output <mp4> --expect 1920x1080@30 --voice <dir>/voice/voiceover.wav` checks the narration in the video still lines up with the voice file.
4. In the delivery note say which engine and voice were used, that pronunciation was checked by transcription and not by ear, and whether that voice is fit to publish.

## Mixing

The voiceover is one `<audio>` in the root at `data-volume="1"`. Under a voice, effects come down to about half their unnarrated level and music sits near 0.12 (`sound.md`). Drop effects that land on top of a spoken word.
