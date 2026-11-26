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
| `scripts/longform.py` | Shared engine of the explainer and quiz: per-scene TTS, Whisper word times, `cue_times` (a graphic appears on the word that names it; `cue_index` = exact word position), `assemble`, chapters, render, thumbnail. Writes `remotion/public/long.json`. |
| `scripts/explainer.py` | ~3 min 16:9 EVERGREEN explainer of ONE topic from `topic_bank.py` (Maharashtra + general knowledge, never today's news; scene kinds title/points/steps/compare/timeline/stat/quote/summary). Facts, numbers and quotes validated against the Wikipedia reference text. `python scripts/explainer.py [--text ... --url ...]`. |
| `scripts/wiki_sources.py` | Wikipedia reference text (Marathi article first for names/terms, then English), `credit_line` (CC BY-SA credit for the YouTube description). |
| `scripts/topic_bank.py` | ~178 topics (group `mh` Maharashtra / `gk` general knowledge, by category). `pick` yields unused topics (known = lower-cased en.wikipedia URLs in the `LongForm` sheet), categories rotating daily. Add topics there. |
| `scripts/quiz.py` | ~5 min daily GK + Maharashtra quiz (NOT news): 10 questions from 4 `mh` + 2 `gk` Wikipedia topics, 4 options, 5 s silent countdown, answer + explanation. A bad question is dropped; fewer than 6 good ones = model repair. |
| `scripts/drafts.py` | Script approval for the explainer and quiz: `draft` writes an editable `.txt` in `drafts/` (git-ignored) from the person's topic/URLs, `produce` reads the approved (or self-written) `.txt`. Parsers refuse only what would break the voice/layout (non-Devanagari speech, bad kinds, missing items) and list every line to fix; approved text is not fact-checked again. |
| `scripts/voices.py` | Voice roles of the long videos (explainer, quote, quiz_read, quiz_cheer): voice + delivery style per scene kind, env-overridable (`EXPLAINER_TTS_VOICE`, `QUOTE_TTS_VOICE`, `QUIZ_TTS_VOICE`, `*_TTS_STYLE`). Reels and bulletins keep the plain anchor. `scripts/voice_samples.py` writes samples to `out/voices/` to choose by ear. |
| `scripts/thumbnails.py` | YouTube thumbnails: 2-3 variants per video from composition `MahaSparkThumbnail` (styles bold / question / figure / alert; one short punchy line, one focal element, red tag). The first is uploaded, all are kept in `out/thumbs/` for a manual swap or YouTube Studio's Test & compare. Used by reels, bulletin, explainer and quiz. |
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
  Models: `GEMINI_MODELS` when set; otherwise `discover_gemini_models` asks Google which text models the key can use (newest first, up to 6; `GEMINI_AUTO_MODELS=0` turns it off) and `gemini-2.5-pro,gemini-2.5-flash` are appended as a last resort.

## Phonetic TTS engineering (dual-text output)

`story.json` carries two texts per scene:

- `headline` / `description`: crisp on-screen Marathi with sharp digits (`85%`, `₹1,200 कोटी`).
- `tts_text` (joined into `tts_narration_script`): what the voice reads. It may contain ONLY Devanagari letters,
  spaces, commas and full stops. `tts_problems()` rejects digits (including ०-९), Latin letters, symbols
  and `? !`.
  - Numbers, dates, money, percentages: the MODEL WRITES DIGITS in `tts_text` (`35000`, `₹1,200 कोटी`, `85%`) and `marathi_numbers.numbers_to_words` spells them as correct Marathi (`पस्तीस हजार`, `एक हजार दोनशे कोटी रुपये`, `पंच्याऐंशी टक्के`) inside `validate_story` / `validate_item`, before `tts_problems`. Marathi 11-99 are irregular and the model got them wrong on air (35000 was read as "तीस पॉइंट पाच हजार"), so never ask the model to spell numbers. Times like 10:30 and numbers over 99 crore stay digits and are rejected (the model repairs them in words). Extend the converter and its tests rather than the prompt.
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

After Telegram, `pipeline.upload_reel_to_youtube` uploads the video (and sets a 1280x720 thumbnail from the `BulletinThumbnail` composition: hook headline, red tag, key figure; best effort) (title `social_title`, description from `youtube_upload.build_reel_description`: caption, main point, CTA, AI-voice note, hashtags; NO source link; tags from `seo_keywords`). Best effort: a failure never fails the story. A default YouTube API project has 10,000 quota units/day and an upload costs 1,600, so only ~6 uploads/day fit and the two bulletins must always get in: reels upload at most one per slot hour (`REEL_UPLOAD_SLOTS` = 12, 19 IST; the explainer and quiz take two of the ~6 daily uploads), counted from `YouTube: OK <date>` in the Sheet note. `YOUTUBE_UPLOAD_REELS=0` turns it off; `YOUTUBE_SYNTHETIC_FLAG=1` also ticks YouTube's altered/synthetic box (the AI voice is always disclosed in the description via `AI_NOTE`). Privacy follows `YOUTUBE_PRIVACY`.

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

## Explainer and daily quiz (16:9, YouTube)

Two more long videos on the shared engine `longform.py` and ONE composition, `MahaSparkLong` (`remotion/src/long/`, props `remotion/public/long.json`, outro shared with the bulletin). Each scene has its own voice clip; word times are relative to the scene start and the graphics are cued to spoken words, so nothing appears before it is said. Scene components: `ExplainerScenes.tsx` (kinds), `QuizScenes.tsx` (intro, question with countdown ring, answer reveal, end), `LongCaptions.tsx` (karaoke), `LongVideo.tsx` (sequencing, bed ducking, whoosh, progress line, logo layer). Same rules as everywhere: facts only, digits on screen / spelled in `tts_text`, no date or category badges.

- Workflows `explainer.yml` and `quiz.yml` are `workflow_dispatch` only (GitHub's schedule runs hours late). Start them from cron-job.org like the bulletin (POST `https://api.github.com/repos/jazzit01/mahaspark-engine/actions/workflows/<file>/dispatches`, body `{"ref":"main"}`).
- Sheet worksheet `LongForm` (created on first run) stores used Wikipedia URLs so a topic is not explained or quizzed twice.
- YouTube quota: 2 bulletins + explainer + quiz + 2 reels = 6 uploads a day (`REEL_UPLOAD_SLOTS` was cut to 12 and 19 IST for this).
- Not verified here (no network): the real Remotion render of `MahaSparkLong`, live Gemini output for the explainer/quiz schemas, TTS of the option letters. Check the first runs' logs and look at the first videos.

### Your own topic and script approval (laptop)

`python scripts/explainer.py draft --topic "..." [--url ...]` and `python scripts/quiz.py draft [--topic "..." --url ...]` write `drafts/<kind>-<time>.txt` (the quiz without `--topic` uses the next unused Maharashtra/GK topics; `--topic` reads Wikipedia first, then your `--url` links, a news search only if both are empty). Edit it, save, then `python scripts/explainer.py produce drafts/<file>.txt` / `python scripts/quiz.py produce drafts/<file>.txt` (same `--skip-render/--skip-upload/--skip-telegram`). A script written from scratch in the same format works too. With no sub-command both scripts stay fully automatic (what `explainer.yml` / `quiz.yml` run). Format and rules: the comment block at the top of every draft, `drafts.py`.

### Voices and thumbnails

- Long videos voice each scene in the role of its kind (`voices.role_for_scene`): explainer = default voice with a warm explaining style, `quote` scenes = a second (deeper) voice, quiz questions = a host voice reading clearly, quiz intro/answer/closing = the same voice livelier. `synthesize_voiceover(..., voice=, style=)`; the style only ever travels in the style field (never the spoken text). Not verified here: how each voice sounds in Marathi; run `voice_samples.py` and listen.
- Thumbnails: the explainer model also writes `thumb_text` (3-5 words, a question or the hook; dropped silently if long or if a number is not in the source; editable as `THUMB:` in the draft file). Other videos shorten their headline (`thumbnails.short_text`). Not verified here: the real still render of `MahaSparkThumbnail`.

### Owner rules, answer checking, approval workflows, setup check

- `scripts/content_rules.py` (one place): Savarkar is always written plainly (`plain_names`: no "स्वातंत्र्यवीर"/"वीर" before the name; applied to every model reply in `generate_json`, to `ee.clean_tts_text`, to approved draft files); quizzes never ask about or offer Savarkar, the RSS, Godse (`blocked_in_quiz`) and the topic bank never offers them (`blocked_topic`); news (reels, bulletin) naming Savarkar is skipped in `fetch_news.iter_candidates` (`SAVARKAR_NEWS=plain` publishes it with the plain name instead).
- `scripts/factcheck.py`: every quiz question carries `evidence` (a phrase copied from the reference text, checked in `check_question`) and then an independent model call answers each question blind (`verify_questions`); a question stays only if that checker finds the same single answer stated outright. The explainer script is checked statement by statement (`unsupported_statements`); one rewrite, leftovers appear as `# FACT-CHECK NOTE` lines in the draft file.
- Nothing is published without approval: `explainer.py` / `quiz.py` with no sub-command only write a draft (`--auto` is the old unattended mode). Workflows `explainer.yml` / `quiz.yml` have input `step`: `draft` (writes `approvals/<kind>-<time>.txt`, commits it to main, sends the file and an edit link to Telegram) and `produce` (input `file` = that path; voice, render, YouTube, Telegram). cron-job.org without inputs can only draft.
- Quiz layout: no karaoke captions on question/answer scenes (the explanation sits in its own box under the options).
- `scripts/check_setup.py` / workflow "Check my setup": tests the Gemini, Telegram, Google Sheet and YouTube secrets and says which one is wrong. YouTube `invalid_grant` ("expired or revoked") almost always means the OAuth consent screen is still in Testing (refresh tokens die after 7 days) or the refresh token was made with another client id/secret.
- Not verified here: live Gemini behaviour of the checker, the real render of the changed quiz layout, the draft/produce workflows on GitHub.

### Explainer visuals, manual YouTube kit, simpler approval

- `scripts/topic_images.py`: freely licensed photos (CC / public domain, >= 900 px, no maps/logos/icons) from the topic's English Wikipedia article (lead image first), up to 6, downloaded to `remotion/public/long/photos/`; `longform.attach_photos` spreads them over the scenes (`scenes[i].media`, `props.credits`); `LongBackdrop.tsx` shows each with a slow Ken Burns move, a cross-fade over the previous photo and a dark brand-blue scrim. The description lists the credits. `EXPLAINER_PHOTOS=0` turns photos off; with none found the animated studio is used.
- `longform.pick_studio` rotates the animated studio per video (`props.studio`: PrimeGrid / DataTelemetry / GlassNewsroom) for explainer and quiz. Stat scenes count their figure up (`countUp`, years stay still).
- `scripts/manual_kit.py`: when the YouTube upload fails or is not configured (bulletin, explainer, quiz) the title, description and tags are written to `out/youtube_metadata.txt` (kept as an artifact) and sent to Telegram with the video when it fits the bot limit.
- Approval workflows: `produce` with an empty `file` uses the newest `approvals/<kind>-*.txt`; the Telegram notice lists STEP 1 (edit link) and STEP 2 (what to run).
- Not verified here: live Wikipedia image lookups and the real render of the photo backdrops; check the first explainer video.

### YouTube refresh token on your computer

`python scripts/get_youtube_token.py <CLIENT_ID> <CLIENT_SECRET>` opens the Google sign-in page (loopback redirect, works with a "Desktop app" client) and prints the refresh token. The token only works with the client id/secret it was made with (a mismatch gives `unauthorized_client`), so put all three in the GitHub secrets together.


### Kinetic headlines, Maharashtra map, Shorts cuts

- `kit.tsx` `KineticText`: headline words spring in one after another; the key word (first word with a figure, else the longest word of 3+ words, min 5 chars) is gold. Used by `Headline`, the title scene and the Shorts title.
- `scripts/geo.py` (`PLACES`, keyed by lower-cased en.wikipedia title = topic-bank entries; `pin_for`, `attach_map`) adds `props.map` `{lat, lon, label}` for place topics. `GeoMap.tsx` draws the schematic Maharashtra outline (`MAHARASHTRA_OUTLINE`, hand-simplified, not survey data), a pulsing pin and Mumbai/Pune/Nagpur for orientation on the explainer TITLE scene (replaces the glowing ring). Topics not in `PLACES` keep the ring. Add a place = one line in `PLACES` (a test checks it is a bank topic and inside the map frame).
- `scripts/shorts.py`: after the long video, `pick_clip` chooses a run of whole scenes of 28-58 s (explainer: prefers the hook, stat/quote/compare scenes; quiz: starts on a question, ends on its answer) and `make_short` renders `MahaSparkLongShort` (`LongShort.tsx`: 1080x1920, title on top, the 16:9 video scaled to full width via `LongVideo` with `props.clip`, big karaoke captions below, no outro) from `public/long_short.json`. Telegram only (the YouTube quota is used by the long videos). `LONG_SHORTS=0` turns it off; any failure is a warning only.
- Not verified here (no real render): the look of the map, the kinetic words in Devanagari, the scaled-video Short and its audio offset (`Sequence from={-start}`); check the first explainer/quiz Short.

### Visual pack 2 (long videos), voice quota, thumbnail swap

- **Voice quota (explainer, quiz, bulletin):** a per-minute Gemini 429 no longer marks a (model, key) pair spent for the whole run. `quota_cooldown` reads `retryDelay` (else 65 s) and the pair cools down in `_TTS_COOLDOWN`; only daily (`PerDay`) or `limit: 0` errors are permanent (`_TTS_SPENT`). `allow_tts_wait(seconds)` (called by `longform.voice_all`, 1200 s, and `bulletin.add_voices`, 900 s; env `TTS_WAIT_SECONDS`) lets `synthesize_voiceover` sleep until the earliest pair is free instead of failing. Reels keep a wait budget of 0 and fall back to the voiceless video. `longform.voice_scene` caches each clip in `remotion/public/long/cache/` by hash(text, voice, style); `explainer.yml`/`quiz.yml` restore and save that folder with `actions/cache`, so a retry only voices what is missing. A failed voice step also sends a Telegram notice.
- **Scene kinds:** `chart` (explainer, 2-5 items, `label` + numeric `value` in ONE unit; the figure must be in the source; animated bars + count-up in `ExplainerScenes.tsx`). Drafts accept `=== SCENE n | chart ===`.
- **Per-cut motion:** `Transitions.tsx` rotates wipe / zoom-through / light streak by scene number (14 frames, first scene has none). `LowerThird.tsx`: the topic title (text before ` | `) slides in for 3.4 s at the start of each explainer scene after the title (it is the topic, not a category badge).
- **Opener:** `Sting.tsx` = logo punch-in with ring flash over the first 1.35 s plus `public/sting.wav` (`scripts/make_sting.py`, original synthesis). No time is added (it overlays scene 1). Not in Shorts cuts.
- **Style packs:** `props.pack` (`longform.PACKS`: explainer = knowledge gold/red, quiz = cyan/orange) sets CSS variables `--accent`/`--accent2` on the video root (`kit.tsx` `PACKS`, `packVars`, `ACCENT`, `ACCENT2`); long components use those instead of `COLORS.gold/red`.
- **Quiz polish:** countdown ring shifts cyan -> amber -> red and pulses in the last 2 s, the correct option glows, a dot row shows progress (`QuizDots`).
- **Photo depth:** landscape photos in `LongBackdrop.tsx` are two layers (blurred far layer drifting against a feathered sharp near layer) plus faint motes. It is a layered parallax, NOT a subject cut-out (no segmentation model is used).
- **Timeline photos:** timeline cards show the video's topic photos (`gallery`, unique `scenes[i].media`) in round frames; no photos = the old dot.
- **Loop backgrounds:** `.mp4` files in `remotion/public/loops/` (for example made with lemo-opuscar) are picked per video (`longform.pick_loop`, `LONG_LOOPS=0` off) and play muted under a dark scrim (`LoopBackdrop.tsx`); photo scenes cover them. Empty folder = animated studio only. Keep clips small (Telegram's 50 MB limit).
- **Thumbnail swap:** `python scripts/thumb_ab.py swap <video id or URL> [--name long-explainer] [--style bold]` sets the next variant from `out/thumbs/`; it only rotates (no click-rate reading). Use YouTube Studio's Test & compare to measure.
- Not verified here (no real render): all of the above visually (transition overlays, lower third position against captions, chart bar sizes, depth mask, sting timing against the first voice, `color-mix` borders), and the live voice-wait behaviour.

### Line-art studios (look families "Sketch & Board", "Line Diagrams", "Data & Maps", "Light & Lines")

- Inspired by the look families of lemo-opuscar, written as ORIGINAL Remotion/SVG code. Its code is MIT but its style prompts/docs are CC BY-NC 4.0, so they are never copied into this monetised project.
- Explainer and quiz: `ChalkboardStudio` (slate board, self-drawing chalk doodles, dust), `BlueprintStudio` (blueprint grid, meshing gears, isometric cube, dimension lines), `DataMapStudio` (contours, graticule, transit-style routes with stations). Helpers in `studios/lines.tsx` (`DrawPath`, `drawn`, `cycleOpacity`). All are dark so the existing light text, captions and scrims stay readable; palettes are in `theme.ts`. `longform.LINE_STUDIOS` joins `pick_studio` (rotates with the three older studios; Breaking is still never used).
- News bulletin: `bulletin/LightLines.tsx` replaces the plain grid background (circuit traces with travelling light pulses, flow-field lines, drifting light points); `bg_hue` still applies.
- Real lemo films can still be dropped into `remotion/public/loops/*.mp4` (`pick_loop`).
- Not verified here (no real render): the look and motion of all four, SVG filter cost per frame (chalk displacement, glow); check the first renders and drop the filter if rendering is slow.

### Office titles (never promote or demote a leader)

- `content_rules.OFFICES` lists leaders whose office is certain (Eknath Shinde = उपमुख्यमंत्री, Devendra Fadnavis = मुख्यमंत्री). `office_error` flags "मुख्यमंत्री"/"Chief Minister"/"CM" directly before Shinde (and "उपमुख्यमंत्री"/"Deputy CM" before Fadnavis); "माजी", "तत्कालीन", "भावी" in front are allowed. `ee.check_offices` raises a ValueError (the model's one repair) in reel `validate_story`, bulletin `validate_item`, explainer scenes and quiz questions; `drafts.parse_*` lists it as a problem for hand-edited scripts. The prompt's fact section carries the same table (`office_prompt_line`). **Update `OFFICES` (and `tests/test_office_titles.py`) whenever an office changes**; only add people whose office is certain.
- Limit: only a title directly in front of the name is checked ("मुख्यमंत्री एकनाथ शिंदे", "Chief Minister Shinde"); a title that follows the name or a leader not in the table is not.

### Licensing rule (owner decision)

Anything that needs a licence fee, attribution/credit, or forbids commercial use is NOT used in this monetised project. Use only original code and assets (own synthesis, own drawings) or material that needs no credit. The lemo-opuscar style prompts (CC BY-NC) and its CC BY demo films are therefore not used. Wikipedia/Commons photos in the explainer already carry their credit lines in the video description by law; do not add new sources that need credit.

### Quiz: upload only (no new voice, no new render)

Workflow `quiz.yml` step `upload` + input `run_id` (number at the end of an earlier produce run's URL): downloads that run's `quiz` artifact (`out/mahaspark_long.mp4`, `remotion/public/long.json`), then `python scripts/quiz.py upload <approved file>` calls `quiz.publish` (YouTube upload, thumbnail, Telegram, Sheet record; no Short). Use it when a produce run rendered fine but the upload failed. Artifacts live 2 days. Not verified here: the cross-run artifact download on GitHub (needs `actions: read`, already in the workflow).

### Radio "chirr" after a spoken line: what is ruled out (still open)

Heard after the end of every line in all video types, about 470-480 ms after the speech ends. Ruled out: the transition whoosh (listening test: clean) and the Gemini voice clips themselves (a tail cleaner was built in #51/#52 and reverted: real runs logged "0 ms removed", so the clips carry nothing after the speech). Main suspect: the music bed ducking in `LongVideo.tsx` / `BulletinReel.tsx` (`duck()`: the bed gain rises from 45% to 100% over exactly 0.45 s after each word, applied as one gain per frame at 30 fps = 0.75 dB steps, which can sound like zipper noise). Check this before anything else; the fix would be to mix the ducked bed offline with a sample-accurate smooth gain instead of a per-frame `volume` callback.

### Sound stems (diagnostic for the "chirr")

Workflow `quiz.yml` step `stems` (same `file` input as produce; no upload, no Telegram): voices come from the cache, then `MahaSparkLong` is rendered audio-only (`--codec=mp3`) five times with `props.mute` (`voice`/`bed`/`whoosh`/`sting`, honoured only in `LongVideo.tsx`): `full`, `voice_only`, `bed_only`, `whoosh_only`, `sting_only`. Artifact `quiz-stems` (2 days). Listen to each: the chirr is in the part that has it. Not verified here: the audio-only Remotion render on GitHub.

### Explainer motion pack (original code)

- Two more explainer-only studios: `AuroraStudio` ("Aurora Flow": navy with slow colour glows, silky light ribbons, drifting stars) and `OrbitStudio` ("Knowledge Graph": drifting nodes joined by thin lines with light pulses and slow dashed orbit rings). They are in `LINE_STUDIOS["explainer"]` (not the quiz) so `pick_studio` rotates them in. Palettes in `theme.ts`.
- `long/SceneSweep.tsx`: on every explainer scene after the first (not in Shorts cuts) a soft light sweep crosses the frame and four corner brackets draw in and fade over 1.8 s. No text, never over captions.
- All original SVG/React written for this project; nothing from lemo-opuscar's CC BY-NC prompts is used (licensing rule above).
- Not verified here (no real render, `tsc` needs `npm install`): the look and timing of the three additions, SVG blur cost per frame (drop the `filter`s if rendering is slow).

### Instagram Reels (back on, opt-in)

- `scripts/publish_instagram.py` posts the finished video (16:9 reels and 9:16 Shorts) as an Instagram Reel through Meta's resumable upload (no public link needed): container -> upload -> poll `status_code` -> `media_publish`. `pipeline.post_reel_to_instagram` runs after Telegram and YouTube, best effort (a failure only writes `Instagram: FAIL ...` in the Sheet note). Caption = `social_caption` + follow line + up to 30 hashtags, cut to 2200 characters.
- Off unless the repository VARIABLE `ENABLE_INSTAGRAM` is exactly `true`. Secrets: `INSTAGRAM_USER_ID` (Instagram Business/Creator account id), `INSTAGRAM_ACCESS_TOKEN` (long-lived, `instagram_content_publish`; it expires after about 60 days unless refreshed, and an expired token is named in the error). Only the 16:9 reels get the YouTube slot limit; Instagram has no slot limit here (Meta allows 100 API posts a day).
- Not verified here (no network, no account): the live Meta calls and how a 16:9 video looks as a Reel; check the first run's log lines starting `[Instagram]`.

### YouTube Shorts upload (9:16)

- `pipeline.upload_reel_to_youtube` now uploads the 9:16 Shorts too (before: Telegram only). A Short gets `#Shorts` in the description and tags (`build_reel_description(story, short=True)`) and no custom 16:9 thumbnail. Shorts SHARE the reel slots (`REEL_UPLOAD_SLOTS` 12 and 19 IST, one upload per slot hour, counted from `YouTube: OK <date>`), so the daily quota (6 uploads of 1,600 units) is not exceeded: a slot goes to whichever reel or Short is finished first after the slot hour. `YOUTUBE_UPLOAD_SHORTS=0` turns Shorts off, `YOUTUBE_UPLOAD_REELS=0` turns all reel/Short uploads off. More uploads per day need a YouTube API quota increase; then add slot hours.
- Not verified here (no network): the live upload and that YouTube lists the video under Shorts.

### Facebook Page Reels (on) and Instagram (paused)

- `scripts/publish_facebook.py` posts the 9:16 Shorts as Facebook Page Reels (Graph API `video_reels`: start -> rupload -> poll `status.video_status` -> finish `PUBLISHED`, `is_ai_generated: true`). Facebook Reels must be 9:16 and 3-90 s, so 16:9 videos are skipped (`reel_skip_reason`). `pipeline.post_reel_to_facebook` runs after Instagram, best effort (`Facebook: OK/FAIL ...` in the Sheet note); the caption is the same as Instagram's.
- Off unless the repository VARIABLE `ENABLE_FACEBOOK` is exactly `true`. Secrets: `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN` (a Page access token with `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`; a long-lived one does not expire). Limit: 30 API posts per Page per 24 h.
- **Instagram is paused**: `runner.yml` sets `ENABLE_INSTAGRAM: 'false'` on purpose. To resume, replace that line with `ENABLE_INSTAGRAM: ${{ vars.ENABLE_INSTAGRAM }}` and set the variable to `true`. The code in `publish_instagram.py` is unchanged.
- Not verified here (no network, no account): the live Meta calls; check the first run's `[Facebook]` log lines.

### Motion behind the headline (reels)

- `remotion/src/HeadlineMotion.tsx` is rendered inside every scene's Sequence, BEHIND the `SceneCard` text and above the studio/footage: two soft colour glows drifting at different speeds (a slow parallax, direction alternates by scene), one light sweep as the scene arrives (about 1.5 s) and a glow right behind the headline that swells with the anchor's voice (`speechEnvelope`: 1 on a spoken word, easing to 0 over 0.35 s of silence; a continuous function of time, so no flicker). Pure CSS gradients (cheap), deterministic (`random(seed)`, no `Math.random`), no text and no badge. Over footage/photos (`overMedia`) everything is about half as strong so the picture stays clean. It uses the story's `words`, so it also works for the voiceless fallback (estimated timings).
- Not verified here (no real render): how strong the glows and the sweep look on each studio; tune the opacities in `HeadlineMotion.tsx` (0.05-0.2 range) if too busy.
