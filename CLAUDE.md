# MahaSpark Engine: maintenance guide

A scheduled pipeline that turns one verified Marathi news story per run into a prime-time news video and delivers it to Telegram: a 16:9 video of about one minute (1920x1080, 30 fps, shared 8 s outro) when the sources are rich, otherwise a 9:16 Short (1080x1920, no outro).

```
RSS -> Sheet queue -> article text -> 5W1H + phonetic script (Gemini) -> Gemini TTS voiceover
    -> faster-whisper word timings -> Remotion render (studio chosen by visual_theme)
    -> out/mahaspark_reel.mp4 -> Telegram (video without caption, then the message: 5W1H, source URL, SEO title/description/keywords/tags) -> Sheet DONE
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
| `scripts/media_fetch.py` | Per-scene visuals: a freely licensed Wikimedia Commons photo of `public_figure` (hook + closing scene), optional Pexels portrait stock video (`PEXELS_API_KEY`, not required) and, with no key, a Commons photo of the scene topic (`visual_query` + `visual_place`). Writes `scenes[i].media` + `media_credits` into `story.json`; every failure just leaves the studio background. |
| `scripts/make_whoosh.py` | Regenerates `remotion/public/whoosh.wav` (the committed file is its output). |
| `scripts/bulletin.py` | The long 16:9 **news bulletin** orchestrator (see News bulletin). `python scripts/bulletin.py [--skip-render] [--skip-upload] [--skip-telegram]`. |
| `scripts/bulletin_editorial.py` | One bulletin item (headline + ONE context line + spoken sentences). Reuses the reel prompt's fact and phonetic sections verbatim. |
| `scripts/youtube_upload.py` | YouTube Data API resumable upload with an OAuth refresh token (env only). |
| `remotion/` | Remotion v4 TypeScript project (see Broadcast design). `src/bulletin/` is the 16:9 bulletin. |
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
- **Length.** Reels are about one minute: 140-185 spoken words (`REEL_MIN_WORDS`; `validate_story(min_words=...)`), 2-8 scenes, headline at most 56 characters, description at most 92. A story whose sources cannot fill that (source text under `THIN_SOURCE_CHARS`, or a long attempt that still comes out short) is written as a **9:16 Short** instead (`story["format"] == "portrait"`): hook + 1-3 scenes, 25-100 words (`SHORT_MAX_WORDS`, `SHORT_MAX_SCENES`), prompt override via `build_user_prompt(short=True)`; the Short renders as composition `MahaSparkShort`, has no outro and goes to Telegram only (no YouTube upload). A thin source (under `THIN_SOURCE_CHARS`) first gets up to two other reports of the same event via `fetch_news.enrich_thin_source` (Google News search on the headline, labelled in the source text). Bulletin items keep their short length.
- **Visuals (reels: OFF by default).** `pipeline.add_visuals` does nothing unless `REEL_VISUALS=1`: reels use the animated studios only because photos did not match the news. The rest of this bullet and `media_fetch.py` still describe the optional/bulletin path. The model writes a generic English `visual_query` per scene and, only for a named public figure acting in
  their public role, `public_figure`. `clean_public_figure` drops it for serious/crime/breaking stories (never a
  face for victims or accused). Stock footage is representative, never presented as the event; the Telegram summary
  says so and lists credits. Footage reels render at CRF 21 (Telegram's 50 MB limit); the light studio is swapped
  for `GlassNewsroomDepth` when footage is attached.
- **Motion graphics.** Per scene the model may add one `motion` graphic: `stat` (a figure that is in the source) or `quote` (words verbatim from the source plus the named speaker).
  `clean_motion` drops anything the source does not back, silently (no repair churn). Rendered by `MotionGraphic.tsx`.
- **SEO output** (Telegram only): `social_title` (60-95 chars, keyword first), `social_caption` (3-4 sentences),
  `seo_keywords` (8-12, Marathi + English), `hashtags` (10-15, always starting `#MahaSpark`).
- **Gemini keys.** `GEMINI_API_KEY` plus optional `GEMINI_API_KEYS` (comma separated, keys from different Google Cloud projects). Text: every model is tried with every key (`gemini`, `gemini-key2`, ...); a spent or rejected key is skipped alone. Voice: model-major over keys, spent (model, key) pairs are remembered for the run (`_TTS_SPENT`).
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

- Two formats from the same components: `MahaSparkReel` 1920x1080 (16:9) and `MahaSparkShort` 1080x1920 (9:16, original vertical layout, no outro). `src/layout.ts` (`useLayout`, from the composition size) holds every size that differs (safe zones 175/56/80 landscape vs 290/450/60 portrait, logo plate, headline/caption sizes); studios read `useVideoConfig()`.
- 1920x1080 (16:9), 30 fps; the story is followed by the shared bulletin outro (`OUTRO_SECONDS` = 8). Scripts are ~150-175 words, 2-8 scenes, total cap 185 words. Font: Noto Sans Devanagari through `@remotion/google-fonts` (loaded in `src/fonts.ts`).
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
- **Safe zones** (`src/constants.ts`): headlines (84-108 px bold, `headlineSize` by length; was 74 px until the owner asked for a bigger headline), the 46 px sub-heading and captions stay
  inside `SAFE_TOP=175` / `SAFE_BOTTOM=56` / `SAFE_SIDE=80` (`src/constants.ts`).
- Scene layout (`SceneCard.tsx`): progress bar (one segment per scene, no number), then a vertically centred stack: big main headline with an animated accent bar, the context line as a 46 px sub-heading, and the optional motion graphic. No boxes, no 5W1H chips on screen (the 5W1H stays in the Telegram summary). Captions unchanged.
- Footage (`Backdrop.tsx`): per-scene video/photo behind the text with a slow zoom, 9-frame cross-fade and a dark scrim (`overMedia` in `theme.ts` gives light text). Portrait video fills the screen; landscape photos are framed (sharp near-square crop over a blurred, darkened copy). Videos are muted and looped.
- Motion: spring card entrances, animated vertical accent bar, scale/fade exits, word-by-word karaoke captions
  (`Captions.tsx`), `whoosh.wav` on every scene cut, mood bed (`public/bed/<audio_mood>.mp3`, `BED_VOLUME` 0.26, ducked to `BED_DUCK` 45% while the anchor speaks)
  with a 1 s fade-out.
- The white studio `EditorialDeskLight` is retired (not in `CALM_THEMES`, not offered to the model); its component stays only so old story files still render.
- **Backgrounds:** `bg_hue` in `story.json` (and `bulletin.json`, +18 deg per item) hue-rotates only the studio layer, from a hash of the story, so no two videos look alike. Breaking keeps its crimson (`bg_hue` 0).
- **Numbers on screen** are Devanagari digits (`१२`, `₹१,२०० कोटी`, `८५%`) via `marathi_numbers.py`: `words_to_digits` for headline/description/stat, `caption_words` (merged spoken numbers with first-start/last-end timings, stored as `caption_words` in `story.json`) for karaoke captions. `tts_text` is never touched.
- **Music:** the beds in `public/bed/` are generated by `scripts/make_beds.py` (original synthesis, no samples) because the old ripped tracks caused a Content ID claim. Never add third-party music; use the YouTube Audio Library only with attribution rules checked.

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

## News bulletin (16:9, YouTube)

Separate from the reels (the reel pipeline is untouched). Twice a day, 05:00 and 17:00 IST (`bulletin.yml`, cron `30 23` and `30 11` UTC), one job:

```
RSS (round-robin over feeds, de-duplicated) -> 10 items (bulletin_editorial) -> one Gemini TTS clip per item
 -> Commons photo per item (figure, else topic) -> remotion/public/bulletin.json -> ONE Remotion render (MahaSparkBulletin, 1920x1080)
 -> YouTube upload (title, chapters, tags) -> Telegram link -> Sheet worksheet "Bulletins"
```

- Each item shows a big headline (<= 56 chars) and ONE context line (<= 100 chars) beside a photo (layout: text left, photo right behind a gold cut line,
  animated rings when there is no photo), a bottom ticker with the next headlines and a bulletin progress line. No intro; one fixed outro (`Outro.tsx`,
  8 s) is reused by every bulletin. The logo sits on one steady layer above all items. No date/time badges, no slide numbers, no category pill.
- Items use the same fact discipline, banned phrases and phonetic TTS rules as reels (`FACT_RULES`/`PHONETIC_RULES` are sliced from `SYSTEM_INSTRUCTION`,
  so they cannot drift). `validate_item` enforces lengths, `tts_problems`, forbidden phrases and numbers-in-source.
- Item length is max(10 s, 0.5 s + voice + 0.9 s) so every YouTube chapter is >= 10 s. Fewer than `MIN_ITEMS` (5) usable stories = no bulletin (exit 1).
  If the voice quota runs out the bulletin keeps the items voiced so far.
- Bulletin photos are strict: a Commons photo of the `public_figure` (file name contains the surname), or a photo whose file name contains the story's `visual_place`. Loosely related "topic" photos are NOT used (about 80% were wrong). Items without a photo get a designed panel: the key figure of the story (`highlight_for`, e.g. ५० लाख) in large gold type over animated rings, else the category word.
- Duplicate events are dropped: each item carries an English `event_key` and `same_event` skips a second report of the same event. After a successful upload a 1280x720 thumbnail (`BulletinThumbnail`, top story + photo + "आजच्या N मोठ्या बातम्या") is rendered with `remotion still` and set via `thumbnails.set` (best effort; needs a verified channel).
- The YouTube description has chapters, key points, photo credits and the follow/subscribe CTA with `@MahaSparkOfficial`; it has NO source links. Reel captions and the Telegram description block end with the same CTA (`send_telegram.CTA_TEXT`); the outro shows the handle.
- Sheet worksheet `Bulletins` (created on first run) stores used headlines/URLs so the next bulletin only has new stories.
- YouTube: `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` (scope `youtube.upload`), `YOUTUBE_PRIVACY` (default `private`; unaudited API
  projects can only upload private videos). Without credentials the video is only kept as the `bulletin` workflow artifact (2 days) and Telegram says so.
- GitHub minutes: one render job per bulletin (about 15-25 min on the 2-core runner), twice a day, in addition to the 16 hourly reel runs.
- Not verified here (no network): live Commons photos, the YouTube upload, the real Remotion render. Check the first run's logs.

## YouTube upload of the 16:9 videos

After Telegram, `pipeline.upload_reel_to_youtube` uploads the video (and sets a 1280x720 thumbnail from the `BulletinThumbnail` composition: hook headline, red tag, key figure; best effort) (title `social_title`, description from `youtube_upload.build_reel_description`: caption, main point, CTA, AI-voice note, hashtags; NO source link; tags from `seo_keywords`). Best effort: a failure never fails the story. A default YouTube API project has 10,000 quota units/day and an upload costs 1,600, so only ~6 uploads/day fit and the two bulletins must always get in: reels upload at most one per slot hour (`REEL_UPLOAD_SLOTS` = 07, 12, 19 IST), counted from `YouTube: OK <date>` in the Sheet note. `YOUTUBE_UPLOAD_REELS=0` turns it off; `YOUTUBE_SYNTHETIC_FLAG=1` also ticks YouTube's altered/synthetic box (the AI voice is always disclosed in the description via `AI_NOTE`). Privacy follows `YOUTUBE_PRIVACY`.

## CI (`.github/workflows/runner.yml`)

Hourly cron, daytime only (05:00-20:00 IST = cron `30 23` and `30 0-14` in UTC, 16 runs a day) + manual dispatch, 60 min timeout, one run at a time. It caches pip, `~/.npm`, Remotion's browser
(`remotion/node_modules/.remotion`), the Whisper model (`~/.cache/huggingface`) and `~/.cache/ms-playwright`
(kept as requested; Playwright is no longer used, so it stays empty). It runs the unit tests, then
`python scripts/pipeline.py`. Secrets: `GCP_CREDENTIALS`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`,
optional `TELEGRAM_CHAT_ID` (defaults to the project's existing chat), optional `PEXELS_API_KEY` (stock footage; without it reels keep the studio backgrounds), optional `GROQ_/CEREBRAS_/OPENROUTER_API_KEY`.
Variables: `GEMINI_MODELS`, `GEMINI_TTS_MODEL`, `GEMINI_TTS_VOICE`.

`MAX_STORIES_PER_RUN` (default 2, the number queued per run) counts every story attempted, failures included, so one broken story can't burn
through the queue and the TTS quota. No new story is started once `RUN_BUDGET_SECONDS` (default 1800) is used; the rest stay PENDING. A run where the attempted story failed exits with code 1 (red in Actions).

Sheet status flow: `PENDING -> PROCESSING -> DONE | ERROR | REJECTED`. If no AI provider is usable, the row
returns to `PENDING` and is retried next run; `ERROR` rows are never retried.

## Rules for future changes

- Never hard-code tokens. Credentials come from the environment only (`tests/test_send_telegram.py` scans for them).
- Add or change an editorial rule in BOTH the prompt and the validator, and add a test.
- Keep `tts_text` free of digits, Latin letters and symbols. Keep on-screen text separate from spoken text.
- Do not add date badges or extra brand text to the overlay.
- Keep new visual text inside the `src/constants.ts` safe zone.
- Not verified here (no network in the build environment): the live Pexels/Commons calls and a real footage render, the live Gemini TTS call, the Remotion render and
  `npx remotion skills add`. Check the first CI run's logs after any dependency or API change.

## Subject-based bulletin photos

Each bulletin item carries `photo_query` (English subject, e.g. "IndiGo Airbus A320") and `photo_keywords` (lowercase words that must appear in the Commons file name; `clean_photo_subject` validates). Person photos need EVERY name part in the file name. No match = the key-figure panel. Not verified here: live Commons results and the 16:9 render; check the first CI run.
