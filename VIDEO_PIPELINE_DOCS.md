# MahaSpark Video Generation Engine

## Architecture Summary

The production video path is:

```text
GitHub Actions
  -> sheet_processor.py
  -> Google Sheets PENDING row
  -> news_writer.py / Gemini
  -> image_generator.py / random still image
  -> renderer.py / Playwright HTML rasterization
  -> video_renderer.py / FFmpeg composition
  -> Telegram + Instagram publishing
  -> Google Sheets DONE
```

Important distinction: the engine does **not** select or assemble background video clips. It selects a still image and applies a slow Ken Burns zoom with FFmpeg.

## 1. File and Directory Map

### Production pipeline

- `sheet_processor.py`
  - Main autonomous entry point.
  - Fetches RSS news, scans Google Sheets for `PENDING` rows, generates content, renders image plates, creates the video, publishes it, updates status, and deletes temporary files.

- `news_fetcher.py`
  - Reads Google News and Lokmat RSS feeds.
  - Deduplicates headlines against existing Sheet rows.
  - Appends new rows with `PENDING` status and timestamps.

- `news_writer.py`
  - Calls Gemini through `google-genai`.
  - Produces Marathi headline parts, hook, exactly two bullets, captions, hashtags, and audio mood.
  - Valid moods are `serious`, `crime`, `breaking`, `upbeat`, and `neutral`.

- `image_generator.py`
  - Despite its name, it does not currently generate images with FLUX or another model.
  - Selects a random image from `assets/images/backgrounds/`, falling back to `assets/images/`.
  - Current assets include `bg1.png` through `bg6.jpg` and `logo.png`.

- `renderer.py`
  - Launches Chromium through Playwright.
  - Loads `template.html` at 1080x1920.
  - Injects the background, logo, headline, hook, badge, and bullets.
  - Exports seven PNG plates:
    - Full preview
    - Raw background
    - Static frame
    - Headline
    - Hook pill
    - Bullet 1
    - Bullet 2

- `video_renderer.py`
  - Builds and executes the FFmpeg command.
  - Zooms the raw background.
  - Fades in the text plates at different times.
  - Stacks all plates with `overlay`.
  - Adds mood-specific MP3 audio and fades it out.
  - Exports MP4 and a JPEG thumbnail.

- `telegram_notifier.py`
  - Uploads the MP4 to Telegram.
  - Converts HTML highlight spans into Telegram `<b>` tags.
  - Sends YouTube Shorts metadata as a second message.

- `instagram_publisher.py`
  - Uses the Meta Graph API resumable upload flow.
  - Uploads the local MP4, polls processing status, then publishes the Reel.

### Supporting and alternate paths

- `auto_pipeline.py`
  - Older/manual image-only pipeline.
  - Generates content, chooses a background, renders a PNG, and optionally sends it to WhatsApp.
  - It does not call `create_news_reel()`.

- `notifier.py`
  - Sends rendered still images through Green-API WhatsApp integration.

- `main_test.py`
  - Manual image-rendering test.
  - Does not generate a video.

- `test_ig.py`
  - Standalone Instagram image-container publishing test.
  - Not part of the production video pipeline.

- `auto_publisher.yml`
  - GitHub Actions workflow.
  - Runs every ten minutes.
  - Installs Python and Playwright dependencies.
  - Reconstructs credentials.
  - Executes `python sheet_processor.py`.

- `requirements.txt`
  - Lists Python dependencies such as `gspread`, `feedparser`, `playwright`, `requests`, and `google-genai`.

### Asset directories

```text
assets/images/
  bg1.png
  bg2.jpg
  bg3.jpg
  bg4.jpg
  bg5.jpg
  bg6.jpg
  logo.png

assets/audio/
  serious.mp3
  crime.mp3
  breaking.mp3
  upbeat.mp3
  neutral.mp3
```

There is no background-video directory or video asset selection code.

## 2. End-to-End Workflow

### Step 1: Scheduled execution

`auto_publisher.yml` triggers every ten minutes and runs `sheet_processor.py`.

### Step 2: RSS ingestion

`run_autonomous_pipeline()` first calls `fetch_and_queue_news()`.

`news_fetcher.py`:

1. Authenticates with Google Sheets using `credentials.json`.
2. Reads existing records.
3. Fetches the configured RSS feeds.
4. Checks the latest five entries per feed.
5. Removes duplicate titles and summaries.
6. Appends a 13-column row:
   - Status
   - Raw news input
   - Empty editorial fields
   - Created timestamp
   - Error log

New rows start as `PENDING`.

### Step 3: Selecting a pending row

`sheet_processor.py`:

1. Reads all Sheet values.
2. Locates the `Status` and `Raw_News_Input` columns by header.
3. Finds rows with `PENDING` status and non-empty raw text.
4. Immediately changes the row status to `PROCESSING`.

### Step 4: Editorial generation

`generate_news_content(raw_input)` calls Gemini.

`news_writer.py` requests structured JSON containing:

```text
badge
headline_part1
headline_part2
hook_pill
bullets[]
audio_mood
visual_prompt
yt_shorts_title
yt_shorts_description
yt_shorts_tags
ig_reels_caption
ig_hashtags
```

The headline is split into:

- `headline_part1`: white text
- `headline_part2`: theme-colored text

The generated mood is validated against the five allowed values. Invalid values become `neutral`.

The function retries across candidate models and up to three attempts per model for transient errors such as `429` and `503`.

### Step 5: Background selection

`sheet_processor.py` calls `generate_ai_background()`.

`image_generator.py`:

1. Checks `assets/images/backgrounds/`.
2. Falls back to `assets/images/`.
3. Filters for `.jpg`, `.jpeg`, `.png`, or `.webp`.
4. Excludes filenames containing `logo` in fallback mode.
5. Chooses one candidate with `random.choice()`.

The `visual_prompt` and `entity_query` arguments are currently ignored.

### Step 6: HTML plate rendering

`renderer.py` opens the 1080x1920 HTML template and injects:

- Background image
- Logo
- Badge
- Headline parts
- Hook
- Bullet HTML

It then changes the body class and captures each layer independently:

```text
mode-all       -> full preview
mode-raw-bg    -> raw background
mode-frame     -> scrim + logo + badge
mode-hl        -> headline
mode-pill      -> hook pill
mode-b1        -> first bullet
mode-b2        -> second bullet
```

Only the first two bullets are rendered because of:

```python
bullets = pack.get("bullets", [])[:2]
```

The files are generated beside the requested output:

```text
output/reel_12_raw_bg.png
output/reel_12_frame.png
output/reel_12_hl.png
output/reel_12_pill.png
output/reel_12_b1.png
output/reel_12_b2.png
```

### Step 7: Sheet metadata update

Before video rendering, the generated copy is written back into columns `C:K`.

This stores:

- Badge
- Full headline
- Hook
- JSON bullets
- YouTube title
- YouTube description
- YouTube tags
- Instagram caption
- Full preview image path

### Step 8: Video rendering

`sheet_processor.py` selects the mood and calls:

```python
create_news_reel(rendered_layers, mood, video_path)
```

`video_renderer.py` randomly selects a duration from:

```python
[9.9, 10.15, 11.6, 12.12, 13.0, 14.2, 14.9]
```

The output is normally:

```text
output/reel_<row>.mp4
```

### Step 9: Publishing

The completed MP4 is sent to:

1. Telegram through `send_news_video()`.
2. Instagram through `post_reel_to_instagram()`.

Instagram uses a five-second thumbnail offset.

### Step 10: Completion and cleanup

On success:

- Sheet status becomes `DONE`.
- Column M receives Telegram and Instagram results.
- Temporary PNG plates, MP4, and thumbnail are deleted.

On failure:

- Sheet status becomes `ERROR`.
- Column M receives the exception type and message.

## 3. Visual Layer and Canvas Breakdown

The canvas is fixed at:

```text
1080 x 1920
```

Defined in `template.html` and in Playwright in `renderer.py`.

### Z-order stack

#### Layer 1: Background image

```css
.bg-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 1080px;
  height: 1920px;
  object-fit: cover;
  object-position: center;
  z-index: 1;
}
```

This is the only moving visual layer.

#### Layer 2: Studio scrim

A full-canvas vertical gradient:

```text
Top:    rgba(7, 10, 20, 0.70)
25%:    rgba(7, 10, 20, 0.25)
55%:    rgba(7, 10, 20, 0.75)
Bottom: rgba(7, 10, 20, 0.95)
```

It is included in the static frame plate.

#### Layer 10: Broadcast content

The content container has:

```css
width: 1080px;
height: 1920px;
padding: 95px 120px 240px 80px;
z-index: 10;
```

This means the usable content area is approximately:

```text
Left:   80px
Right:  120px
Top:    95px
Bottom: 240px
Content width: 880px
```

### Top bar

The top bar begins at approximately `y = 95px`.

```css
height: 120px;
margin-bottom: 180px;
```

The editorial content therefore begins around:

```text
95 + 120 + 180 = 395px
```

#### Logo

```css
height: 110px;
max-width: 360px;
object-fit: contain;
```

It receives a black drop shadow.

#### Badge

```css
background: #D90429;
color: #FFFFFF;
font-size: 28px;
font-weight: 800;
padding: 7px 22px;
border-radius: 6px;
```

It is right-aligned within the top bar.

### Headline

The editorial region has a maximum width of `900px`, though the parent content width limits it to approximately `880px`.

First line:

```css
font-size: 80px;
font-weight: 900;
color: #FFFFFF;
```

Second line:

```css
font-size: 90px;
font-weight: 900;
```

The second line color depends on the theme:

- Yellow: `#FFC000`
- Red: `#EF4444`
- White: `#FFFFFF`

Both lines use a heavy black text shadow.

### Hook pill

The hook follows the headline with:

```css
font-size: 28px;
font-weight: 700;
padding: 7px 18px;
background: rgba(15, 23, 42, 0.82);
border-radius: 0 6px 6px 0;
```

The left border is theme-colored and `5px` wide.

### Divider

```css
width: 120px;
height: 4px;
margin-bottom: 34px;
```

Its color follows the selected theme.

### Bullets

The bullet list uses:

```css
gap: 28px;
```

Each row uses:

```css
gap: 16px;
```

The icon is:

```css
font-size: 32px;
```

The bullet text is:

```css
font-size: 34px;
font-weight: 700;
line-height: 1.36;
color: #F8FAFC;
```

The `<span class="hl">...</span>` phrase is rendered with weight `800` and the theme highlight color.

### Actual video layer order

The final FFmpeg stack is:

```text
raw background with zoom
  -> static frame: scrim + logo + badge
  -> headline
  -> hook pill
  -> bullet 1
  -> bullet 2
```

All overlays are placed at `x=0, y=0` because every plate already occupies the full 1080x1920 canvas.

## 4. FFmpeg and Filtergraph Analysis

The implementation is in `video_renderer.py`.

### Inputs

FFmpeg receives six indefinitely looped image inputs:

```text
[0:v] raw background
[1:v] static frame
[2:v] headline
[3:v] hook pill
[4:v] bullet 1
[5:v] bullet 2
```

When audio exists, input 6 is the mood MP3 and uses:

```text
-stream_loop -1
```

### Background animation

```text
scale=4320:-2
```

Scales the background to a large width while preserving aspect ratio. The oversized image gives `zoompan` room to crop without exposing edges.

```text
zoompan=
  z='min(zoom+0.0003,1.035)'
  :x='iw/2-(iw/zoom/2)'
  :y='ih/2-(ih/zoom/2)'
  :d=<total_frames>
  :s=1080x1920
  :fps=30
```

Meaning:

- `z`: increases zoom gradually.
- `min(..., 1.035)`: caps zoom at `1.035`, a 3.5% maximum zoom.
- `x` and `y`: keep the crop centered.
- `d`: number of generated frames.
- `s=1080x1920`: output canvas size.
- `fps=30`: generates a 30 FPS stream.

Then:

```text
format=yuva420p
```

converts the stream to a YUVA pixel format suitable for overlay processing.

### Overlay fade-ins

Each text plate is formatted and faded independently:

```text
[2:v] format=yuva420p,
      fade=t=in:st=0.6:d=0.35:alpha=1 [hl]

[3:v] format=yuva420p,
      fade=t=in:st=1.6:d=0.35:alpha=1 [pill]

[4:v] format=yuva420p,
      fade=t=in:st=3.0:d=0.35:alpha=1 [b1]

[5:v] format=yuva420p,
      fade=t=in:st=4.6:d=0.35:alpha=1 [b2]
```

Timeline:

```text
0.00s   Background and static frame visible
0.60s   Headline begins
1.60s   Hook pill begins
3.00s   Bullet 1 begins
4.60s   Bullet 2 begins
```

The fade duration for every element is `0.35` seconds.

### Cumulative compositing

```text
[zoomed_bg][static_frame]
  overlay=0:0:eof_action=pass:repeatlast=1 [base];

[base][hl]
  overlay=0:0:eof_action=pass:repeatlast=1 [s1];

[s1][pill]
  overlay=0:0:eof_action=pass:repeatlast=1 [s2];

[s2][b1]
  overlay=0:0:eof_action=pass:repeatlast=1 [s3];

[s3][b2]
  overlay=0:0:eof_action=pass:repeatlast=1 [v]
```

Parameters:

- `overlay=0:0`: full-canvas alignment.
- `eof_action=pass`: keeps the existing video when an overlay ends.
- `repeatlast=1`: repeats the last overlay frame if necessary.

### Audio

The mood map is:

```text
serious  -> assets/audio/serious.mp3
crime    -> assets/audio/crime.mp3
breaking -> assets/audio/breaking.mp3
upbeat   -> assets/audio/upbeat.mp3
neutral  -> assets/audio/neutral.mp3
```

Audio uses:

```text
afade=t=out:st=<duration - 0.8>:d=0.8
```

So the final 0.8 seconds fade out.

There is no:

- Voiceover
- Audio ducking
- Sidechain compression
- Audio mixing
- Volume normalization
- Explicit audio fade-in

The MP3 loops indefinitely and the final output is cut with `-t`.

### Encoding

```text
-t <duration>
-c:v libx264
-preset fast
-crf 19
-pix_fmt yuv420p
-c:a aac
-b:a 192k
-movflags +faststart
```

Meaning:

- `-t`: enforces the selected duration.
- `libx264`: H.264 video encoding.
- `preset fast`: favors rendering speed over compression efficiency.
- `crf 19`: relatively high visual quality.
- `yuv420p`: broad playback compatibility.
- `aac -b:a 192k`: AAC audio at 192 kbps.
- `+faststart`: moves MP4 metadata to the beginning for faster progressive playback.

### Thumbnail generation

A second FFmpeg call extracts one frame:

```text
-ss 00:00:05.200
-vframes 1
-q:v 2
```

The thumbnail is taken at 5.2 seconds and saved beside the MP4 as `_thumb.jpg`.

## 5. Key Functions and Configuration Index

### Pipeline control

- `run_autonomous_pipeline()` in `sheet_processor.py`
  - Main production coordinator.
  - Change here for pipeline ordering, Sheet status behavior, publishing, or cleanup.

- `run_full_pipeline()` in `auto_pipeline.py`
  - Manual still-image workflow.
  - Not used by the scheduled video workflow.

### News ingestion

- `fetch_and_queue_news()` in `news_fetcher.py`
  - Change RSS feeds, maximum items, deduplication, or Sheet row layout here.

- `RSS_FEEDS` in `news_fetcher.py`
  - Source feed configuration.

- `SHEET_ID` and `CREDS_FILE`
  - Google Sheets and service-account configuration.

### Editorial generation

- `generate_news_content()` in `news_writer.py`
  - Change the output schema, retry behavior, model selection, or prompt here.

- `EDITORIAL_SYSTEM_INSTRUCTION` in `news_writer.py`
  - Controls headline structure, bullet count, Marathi style, highlights, and mood classification.

- `CANDIDATE_MODELS` in `news_writer.py`
  - Gemini fallback order.

- `VALID_AUDIO_MOODS` in `news_writer.py`
  - Accepted mood values.

### Asset selection

- `generate_ai_background()` in `image_generator.py`
  - Change random selection, directory priority, filtering, or future image-generation behavior here.

- `PRIMARY_DIR`, `FALLBACK_DIR`, and `VALID_EXTENSIONS`
  - Background asset configuration.

### Visual layout

- `render_news_tile()` in `renderer.py`
  - Controls HTML injection, plate generation, viewport size, and output naming.

- CSS in `template.html`
  - Change canvas size, coordinates, fonts, colors, spacing, shadows, and layout here.

Key layout selectors:

```text
.bg-image
.studio-scrim
.broadcast-container
.top-bar
.brand-logo
.news-badge
.headline-part1
.headline-part2
.hook-pill
.broadcast-divider
.bullet-row
.bullet-text
```

### Animation and video timing

- `create_news_reel()` in `video_renderer.py`
  - Change input layers, FFmpeg arguments, output encoding, and thumbnail creation here.

- `DURATION_POOL` in `video_renderer.py`
  - Controls randomized reel durations.

- `AUDIO_MOOD_MAP` in `video_renderer.py`
  - Maps editorial mood to MP3 files.

- `zoom_filter` in `video_renderer.py`
  - Controls background scale, zoom rate, maximum zoom, crop behavior, resolution, and FPS.

- `filter_complex` in `video_renderer.py`
  - Controls fade timings and layer order.

### Publishing

- `send_news_video()` in `telegram_notifier.py`
  - Telegram upload and metadata formatting.

- `post_reel_to_instagram()` in `instagram_publisher.py`
  - Instagram upload, polling, and publishing.

## Notable Implementation Details

1. `theme` is passed into `create_news_reel()` but only printed. Theme styling is already baked into the PNG plates by Playwright.
2. `headline_theme` is read by `renderer.py`, but the Gemini prompt does not explicitly request it, so the default is normally yellow.
3. The production Sheet pipeline uses random still images, not generated visual prompts.
4. `renderer.py` correctly returns a dictionary of layer paths. The older `auto_pipeline.py` treats the return value like a single image path, so that manual path is inconsistent with the current renderer API.
5. The repository contains hardcoded fallback API credentials in several files. Production credentials should be rotated and supplied only through environment variables or GitHub secrets.
