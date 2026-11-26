# P0 news operations

## Schedule and selection

The MahaSpark News workflow dispatches on the hour in IST. Set the repository Actions variable
`NEWS_PUBLISH_HOURS_IST` to one to four distinct hours from 0 to 23. The default is
`08,12,16,20`. GitHub Actions may delay a run. At most one long-form news video can reserve a slot
and at most four can reserve publication on an IST date. Interrupted uploads count until reconciled.
The remaining 05:00–20:59 IST hours can run the vertical news pipeline.
The bulletin is available through manual dispatch. Quiz and explainer retain their existing approval workflows.

RSS supplies leads. Production requires readable material from at least two publishers and an editorial assessment
of independence, corroboration, Maharashtra relevance and public value. Landscape candidates are prioritized by
Maharashtra politics, crime and accidents, government decisions, then public interest. A slot can go unused.
The script gets a separate factual and editorial check before synthesis. Long-form scripts need substantive verified
context, implications and public impact. Vertical scripts estimated to need 31–60 seconds are condensed before TTS.
A measured overrun gets at most one additional condensation and synthesis. Stories exceeding 60 seconds can be
handed off to that day's landscape slots when the sources support a full feature.

The vertical output requires actual narration and a playable 9:16 video of 15–30 seconds.
Landscape news requires actual narration and a playable 16:9 video of 240–300 seconds.
FFprobe checks metadata and readable packets before upload. The existing one-second studio tail and eight-second landscape outro fit within the output cap;
only those decorative segments can be shortened to fit. Optional quiz
and evergreen Shorts also use the 15–30-second media gate. Their long-form timings are unchanged.

## Credentials and rollout

- Use the existing `GCP_CREDENTIALS` secret. Give its service account editor access to the same
  Google spreadsheet for every publishing workflow and operator. The ledger worksheet
  `NewsEvents` is created on first use. Local operation uses the existing `credentials.json`
  and optional `GOOGLE_SHEET_ID`. If changing the Sheet, configure all news paths together.
- Keep Gemini or configured fallback credentials. News assessment and the independent
  fact-check must both succeed. Gemini TTS supplies the voice audio.
- Keep `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and `YOUTUBE_REFRESH_TOKEN` with the
  existing upload scope. Review `YOUTUBE_PRIVACY` before public release. The default is private.
  The runner defaults `YOUTUBE_UPLOAD_SHORTS` to `0` to leave more quota for landscape videos.
  Review the combined YouTube quota before enabling Shorts or manually dispatching a bulletin
  in addition to the four news slots, quiz and explainer.
- Keep the existing Telegram and optional social-publishing settings. P0 adds no secrets.
- If an external scheduler is connected, check that its dispatch list has no old bulletin entries.

## Event memory and recovery

The append-only `NewsEvents` tab stores JSON state transitions with a stable event ID,
publication-specific record ID, source URLs, entities, action, incident date, factual summary,
category, format, timestamps and publisher receipts. Same-sheet historical reel, bulletin and
known news records are used for matching. Rich event data is available for new records and
legacy records may only have a headline and source. Exact matching precedes cross-language
semantic comparison. An uncertain match blocks production. Material follow-ups retain the event ID
and require a specific new fact backed by independent sources and a written reason.

Atomic named-range creation on the shared spreadsheet serializes reservations and publishing.
GitHub Actions also serializes the two news workflows. The publishing gate rereads the
ledger and checks duplication and slot capacity immediately before upload. A confirmed
upload stores its receipt. A failure before media submission releases a reservation.
A potentially accepted upload stays blocked. YouTube chunk failures are reconciled within
the same resumable session.

For an interrupted or ambiguous transaction, check all configured destinations and every
related platform account. After checking, use the affected record ID to record the known
receipt or release the event:

```bash
python scripts/event_memory.py RECORD_ID --published-id youtube=VIDEO_ID --reason 'Confirmed in YouTube Studio'
python scripts/event_memory.py RECORD_ID --confirmed-absent --reason 'Confirmed absent at every destination'
```

If a terminated process left the range `mahaspark_news_transaction`, first verify there is
no active producer or reconciliation process against the spreadsheet. Remove that named range
in Google Sheets, then reconcile unresolved records before retrying production. Keep the
ledger and its history when recovering a failed run. To retry a rejected upload from the vertical queue,
return its original row to PENDING only after the event reservation is reconciled and the source is still current.

A companion Short is explicit. Provide `--companion-event` with the published landscape
record ID and `--companion-focus` with a specific useful angle to `scripts/pipeline.py --text … --url …`.
The record must refer to the same event and the angle must add distinct, verified value.
Scheduled runs only create independent stories.

## Custom explainer approval

Run `python scripts/explainer.py draft --topic 'शरद पवार राजकीय प्रवास'`. Without a URL, Marathi
subjects are searched in Marathi Wikipedia using the requested phrase and then a narrower
lookup. English subjects use the existing Wikipedia search. The original topic remains
in the generation and repair prompts. Use one or more `--url` arguments when the available
references cannot support the topic. The relevant-source, subject-preservation and factual checks
must succeed before an approval draft is created. Review the draft before running `produce`.
Recoverable model drafts rejected by validation are available under `out/explainer-debug/`
or as the failed workflow's debug artifact.
