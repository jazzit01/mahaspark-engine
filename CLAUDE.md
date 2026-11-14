# MahaSpark Engine: maintenance guide

A scheduled pipeline that turns one verified Marathi news story per run into a prime-time vertical
news reel (1080x1920, 30 fps) and delivers it to Telegram.

```
RSS -> Sheet queue -> article text -> 5W1H + phonetic script (Gemini) -> Gemini TTS voiceover
    -> faster-whisper word timings -> Remotion render (studio chosen by visual_theme)
    -> out/mahaspark_reel.mp4 -> Telegram (video + 5W1H summary + source URL) -> Sheet DONE
```

## Layout

| Path | Role |
|---|---|
| `scripts/pipeline.py` | Orchestrator. `python scripts/pipeline.py` (scheduled), or `--text "<title>\n<article>" --url ... [--skip-render] [--skip-telegram]` for a local one-off that does not touch the Sheet. |
| `scripts/fetch_news.py` | RSS feeds, Google News link resolution (`googlenewsdecoder`), article text extraction. Items whose publisher article can't be read are still queued (written from headline + RSS summary) unless title + summary are under 80 characters. |
| `scripts/sheet_queue.py` | Google Sheet job queue. Columns A-M legacy, N `Source_URL`, O `Visual_Theme`, P `Summary_5W1H`. |
| `scripts/editorial_prompts.py` | The editorial system prompt (Marathi voice, 5W1H, phonetic rules). Edit wording here. |
| `scripts/editorial_engine.py` | Pydantic schema, deterministic validators, `write_story`, `synthesize_voiceover`. |
| `scripts/llm_providers.py` | Gemini first, then Groq, Cerebras, OpenRouter. Quota/auth/404 handling, one repair attempt. |
| `scripts/align_timings.py` | `faster-whisper` (`small`, `int8`, CPU) timestamps aligned to the known script words. |
| `scripts/send_telegram.py` | Video + 5W1H summary + source URL. Credentials from environment only. |
| `scripts/media_fetch.py` | Per-scene visuals: Pexels portrait stock footage from each scene's `visual_query` (`PEXELS_API_KEY`) and a freely licensed Wikimedia Commons photo of `public_figure`. Writes `scenes[i].media` + `media_credits` into `story.json`; every failure just leaves the studio background. |
| `scripts/make_whoosh.py` | Regenerates `remotion/public/whoosh.wav` (the committed file is its output). |
| `remotion/` | Remotion v4 TypeScript project (see Broadcast design). |
| `assets/archive/` | Retired static backgrounds (`bg1-6`). Not used by the pipeline. |
| `tests/` | `python -m pytest -q`. No network or API keys needed. |

Generated, git-ignored: `remotion/public/media/`, `remotion/public/voiceover.wav`, `remotion/public/story.json`, `out/`, `credentials.json`.

## Editorial standards (the #1 priority)

All of these are in `editorial_prompts.py` AND enforced by `validate_story` in `editorial_engine.py`.
A model slip is caught and the model gets one repair attempt with the exact error.

- **Facts only.** Use only the source text. Rumours, unattributed "sources say" leaks and opinion pieces return
  `approved: false` (the row becomes `REJECTED`). A thin source is still written (shorter, 3 scenes) from the headline
  and context; only sources under 60 characters are rejected before any model call. Allegations are attributed to the named person or institution.
- **5W1H.** `five_w_one_h` must answer `what`; when/who/where/why/how are filled only if the source states them and
  are left empty otherwise (never invented, never blocks the story).
- **Voice.** Prime-time anchor Marathi. No creator/YouTuber slang or clickbait. Scene 1 is a 3-4 second hook
  (at most 14 spoken words). Short active sentences. Name the institution or leader inside the sentence.
- **Banned phrases** (`FORBIDDEN_PHRASES`): अधिकृत माहितीनुसार, वृत्तानुसार, सूत्रांनी दिलेल्या माहितीनुसार and similar
  agency clichés, plus old filler/clickbait lines. Extend that list rather than adding prompt-only rules.
- **On-screen numbers** in `headline`/`description` must appear in the source text (no invented figures).
- **Length.** 3-6 scenes, 40-150 spoken words in total, headline at most 56 characters, description at most 92.
- **Visuals.** The model writes a generic English `visual_query` per scene and, only for a named public figure acting in
  their public role, `public_figure`. `clean_public_figure` drops it for serious/crime/breaking stories (never a
  face for victims or accused). Stock footage is representative, never presented as the event; the Telegram summary
  says so and lists credits. Footage reels render at CRF 21 (Telegram's 50 MB limit); the light studio is swapped
  for `GlassNewsroomDepth` when footage is attached.
- **SEO output** (Telegram only): `social_title` (60-95 chars, keyword first), `social_caption` (3-4 sentences),
  `seo_keywords` (8-12, Marathi + English), `hashtags` (10-15, always starting `#MahaSpark`).
- **Sampling.** `temperature=0.15`, structured JSON output through the `Story` pydantic schema.
  Models: `GEMINI_MODELS` (default `gemini-2.5-pro,gemini-2.5-flash`).

## Phonetic TTS engineering (dual-text output)

`story.json` carries two texts per scene:

- `headline` / `description`: crisp on-screen Marathi with sharp digits (`85%`, `₹1,200 कोटी`).
- `tts_text` (joined into `tts_narration_script`): what the voice reads. It may contain ONLY Devanagari letters,
  spaces, commas and full stops. `tts_problems()` rejects digits (including ०-९), Latin letters, symbols
  and `? !`.
  - Numbers, dates, money, percentages are written as full Marathi words ("पंच्याऐंशी टक्के",
    "एक हजार दोनशे कोटी रुपये"). Marathi 11-99 are irregular, so this is the likeliest place for a model error.
    Spot check numbers when changing the prompt.
  - Acronyms are spelled letter by letter ("पी एम आर डी ए", "एफ आय आर"); borrowed words are transliterated
    ("मेट्रो", "हायकोर्ट").
  - No heavy Sanskritised compounds; a comma wherever the anchor breathes; every scene ends with a full stop.

Voiceover (`editorial_engine.synthesize_voiceover`): the engine asks Google which TTS models the API key can see
(`discover_tts_models`, logged as "TTS models visible to this API key"), then tries `GEMINI_TTS_MODEL` (optional, one name
or a comma list), the visible known models and the built-in list (`TTS_MODELS_DEFAULT`: `gemini-3.8-flash-tts`,
`gemini-3.8-flash-lite-tts`, `gemini-3.1-flash-tts-preview`, `gemini-2.5-pro-preview-tts`,
`gemini-2.5-flash-preview-tts`). Each model is tried over two routes: the Interactions API
(`client.interactions.create` with an `annotations: speech_metadata` style block, `ANCHOR_STYLE`; needs
`google-genai>=2.25.0`) and plain REST `generateContent` (`_tts_generate_content`). A missing model, request error or
exhausted per-model quota moves to the next model; transient errors retry; only an invalid key stops the chain.
The spoken text part is ONLY the script (never an instruction line, or the voice reads it aloud); the anchor style goes in the Interactions `annotations` or, on REST, `systemInstruction` (retried without it on HTTP 400). Override voice with `GEMINI_TTS_VOICE`. Output is 24 kHz mono WAV at `remotion/public/voiceover.wav`.

**Voiceless fallback:** if no TTS model works, `pipeline.add_voice_and_timings` does NOT drop the story. It builds
estimated word/scene timings from the script (`align_timings.main_voiceless`, about 2.4 words/s plus pauses), sets
`audio: false` in `story.json`, and renders the full reel (studio, cards, karaoke captions, whoosh SFX, studio bed)
without the voiceover. The Sheet note reads `SUCCESS (voiceless)` and the Telegram summary says the voiceover was
unavailable. If Google changes a TTS API, `_tts_interactions` / `_tts_generate_content` are the only functions to adjust.

## Word timing

Whisper is fed a 16 kHz float array loaded with `load_audio_16k` (not a file path), so faster-whisper never calls PyAV's
`av.open`, which crashed on some installed versions. Whisper's Marathi spelling differs from the script, so its text is never shown. `align_timings.py` fuzzy-matches
Whisper's words to the script words (order-preserving) and uses Whisper's times for matches; unmatched words
are interpolated between neighbours. If Whisper fails, captions fall back to proportional timing. The output
adds `words[]` (`text,start,end,scene`), per-scene `start/end`, `duration_seconds` and `alignment_match` to
`story.json`. Scene texts must add up exactly to `tts_narration_script` or alignment refuses to run.

## Broadcast design (`remotion/`)

- 1080x1920, 30 fps. Font: Noto Sans Devanagari through `@remotion/google-fonts` (loaded in `src/fonts.ts`).
- `story.json` -> props (`--props=public/story.json`). `Root.tsx` sets the video length from
  `duration_seconds + 1s`. Preview compositions `Preview-<theme>` exist for `npm run studio`.
- `visual_theme` (`pick_theme`: grave moods -> Breaking; otherwise rotated over the other four by a hash of the story, skipping the previous reel's studio read from Sheet column O; the model's own pick is ignored for variety) selects one of five full-motion studios in `src/studios/`: `PrimeGridStudio` (navy
  `#080E1A`, 3D grid, gold/cyan rules), `BreakingNewsStudio` (charcoal, crimson waves, scanlines),
  `EditorialDeskLight` (ivory `#F8FAFC`, geometric lines, red bars), `DataTelemetryStudio` (midnight blue,
  radar rings, telemetry nodes), `GlassNewsroomDepth` (indigo depth, light mesh, frosted-glass cards).
  Colours for text and cards per theme live in `src/theme.ts`. No static backgrounds.
- **Branding rules (`SharedOverlay.tsx`, never break these):** only the MahaSpark logo file
  (`public/logo.png`) at top-left with NO extra brand text and NO category pill (removed on request); on one top-level
  `<AbsoluteFill>` above all scenes so it never moves across cuts. **No date, time or timestamp
  badges anywhere.**
- **Safe zones** (`src/constants.ts`): all headlines (74 px bold), 2-line context cards (40 px) and captions stay
  between `top: 290px` and `bottom: 450px`.
- Scene layout (`SceneCard.tsx`): a full-height column fills the area between the logo row and the captions: progress bar (one segment per scene, no number), headline panel, context card and 5W1H fact chips (values only, no labels) from `story.five_w_one_h` (per-scene plan in `Reel.tsx`). Keep it filled; do not shrink back to a top-anchored stack.
- Footage (`Backdrop.tsx`): per-scene video/photo full-bleed under the cards with a slow zoom, 9-frame cross-fade and a dark scrim; cards switch to translucent dark glass (`overMedia` in `theme.ts`). Videos are muted and looped.
- Motion: spring card entrances, animated vertical accent bar, scale/fade exits, word-by-word karaoke captions
  (`Captions.tsx`), `whoosh.wav` on every scene cut, mood bed (`public/bed/<audio_mood>.mp3`) at -20 dB
  with a 1 s fade-out.
- Light studio: the logo is white, so `EditorialDeskLight` puts it on a dark rounded plate.

## Running locally

```bash
pip install -r requirements.txt
cd remotion && npm install && npx remotion browser ensure && cd ..
# optional, once: install Remotion's official agent skills into the project
cd remotion && npx remotion skills add
cp .env.example .env   # fill in keys; the Sheet also needs credentials.json (service account)
python scripts/pipeline.py --text "$(cat article.txt)" --url https://source --skip-telegram
cd remotion && npm run studio   # edit visuals against the sample story
```

## CI (`.github/workflows/runner.yml`)

Hourly cron, daytime only (05:00-20:00 IST = cron `30 23` and `30 0-14` in UTC, 16 runs a day) + manual dispatch, 30 min timeout, one run at a time. It caches pip, `~/.npm`, Remotion's browser
(`remotion/node_modules/.remotion`), the Whisper model (`~/.cache/huggingface`) and `~/.cache/ms-playwright`
(kept as requested; Playwright is no longer used, so it stays empty). It runs the unit tests, then
`python scripts/pipeline.py`. Secrets: `GCP_CREDENTIALS`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`,
optional `TELEGRAM_CHAT_ID` (defaults to the project's existing chat), optional `PEXELS_API_KEY` (stock footage; without it reels keep the studio backgrounds), optional `GROQ_/CEREBRAS_/OPENROUTER_API_KEY`.
Variables: `GEMINI_MODELS`, `GEMINI_TTS_MODEL`, `GEMINI_TTS_VOICE`.

`MAX_STORIES_PER_RUN` (default 1) counts every story attempted, failures included, so one broken story can't burn
through the queue and the TTS quota. A run where the attempted story failed exits with code 1 (red in Actions).

Sheet status flow: `PENDING -> PROCESSING -> DONE | ERROR | REJECTED`. If no AI provider is usable, the row
returns to `PENDING` and is retried next run; `ERROR` rows are never retried.

## Rules for future changes

- Never hard-code tokens. Credentials come from the environment only (`tests/test_send_telegram.py` scans for them).
- Add or change an editorial rule in BOTH the prompt and the validator, and add a test.
- Keep `tts_text` free of digits, Latin letters and symbols. Keep on-screen text separate from spoken text.
- Do not add date badges or extra brand text to the overlay.
- Keep new visual text inside the 290/450 px safe zone.
- Not verified here (no network in the build environment): the live Pexels/Commons calls and a real footage render, the live Gemini TTS call, the Remotion render and
  `npx remotion skills add`. Check the first CI run's logs after any dependency or API change.
