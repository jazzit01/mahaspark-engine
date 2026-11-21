"""MahaSpark daily quiz: ten multiple-choice questions of general knowledge and Maharashtra (history, geography, culture,
institutions, civics, science, India), 16:9, about five minutes. NOT about today's news.

    topic bank (about 4 Maharashtra + 2 general topics) -> Wikipedia reference text -> ONE Gemini call writes the quiz
    (every correct answer is a fact in the reference text) -> per-scene Gemini TTS (the question and its four options are
    read; a silent five second countdown follows) -> Whisper word times -> remotion/public/long.json -> Remotion
    "MahaSparkLong" -> YouTube -> Telegram

Scenes: intro, then for every question a QUESTION scene (voice + countdown) and an ANSWER scene (reveal + one-line
explanation), then the closing scene. ``python scripts/quiz.py [--skip-render] [--skip-upload] [--skip-telegram]``.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from pydantic import BaseModel, Field

import drafts
import content_rules
import editorial_engine as ee
import factcheck
import longform
import manual_kit
import send_telegram
import topic_bank
import wiki_sources
import youtube_upload
from bulletin_editorial import FACT_RULES, PHONETIC_RULES
from config import LONG_PATH
from llm_providers import ContentFailed, ContentRejected, LLMUnavailableError, generate_json
from marathi_numbers import numbers_to_words, words_to_digits

TARGET_QUESTIONS, MIN_QUESTIONS = 10, 6
COUNTDOWN_SECONDS = 5.0
MAX_QUESTION, MAX_OPTION, MAX_EXPLAIN = 96, 38, 110
LETTERS = ["अ", "ब", "क", "ड"]
SPOKEN_LETTERS = ["अ", "ब", "क", "ड"]
MAX_STORIES, MIN_STORY_CHARS = 6, 700
MH_TOPICS, GK_TOPICS = 4, 2  # topics per quiz: Maharashtra and general knowledge
CHANNEL_HASHTAGS = "#MahaSpark #मराठीबातम्या #क्विझ #MarathiQuiz #महाराष्ट्र"
QUIZ_THUMB_TAG = "आजची क्विझ"

QUIZ_INSTRUCTION = f"""
You are the quiz editor of MahaSpark, a No. 1 Marathi news channel. From the REFERENCE TEXTS you are given you write a
general-knowledge quiz about Maharashtra and India (not about today's news) of exactly {TARGET_QUESTIONS} multiple-choice questions that a composed anchor reads aloud. Your output is
machine-read: return exactly one JSON object that follows the supplied schema, nothing else.

{FACT_RULES}

══════════ QUIZ FORMAT ══════════
- Every question is about ONE reference text ("story" = its number) and its correct answer is a fact stated in that text.
  Ask about who, what, where, when, how many, which institution. Never ask for an opinion or a prediction. No question
  about the news of a particular day; ask timeless facts.
- Spread the questions over different reference texts (about 4 questions on Maharashtra topics, the rest general). Easy to medium; a regular viewer must be able to reason out
  or know the answer; mix easy and medium. The question must be complete on its own (name the place or institution; no "this story").
- "question": at most {MAX_QUESTION} characters. "options": exactly 4 short answers (at most {MAX_OPTION} characters each), one
  correct and three plausible but wrong, all of the same kind (all names, all places, all numbers...). Wrong options are plausible other persons, places, institutions or numbers of a similar size.
  "correct": the index 0 to 3 of the right option. Spread the correct index over 0, 1, 2 and 3.
- "evidence": a phrase of 12 to 140 characters copied EXACTLY (same words, same spelling) from the reference text that states the
  correct answer. The answer must be stated outright in the text: no inference, no outside knowledge. Do not write a question
  whose wording claims more than the text says (for example "original name", "first" or "only" unless the text says exactly
  that), and none where the text only hedges ("believed", "according to some"). Exactly ONE option may be correct.
- Never write a question about Savarkar, the RSS or Godse, and never use them as an option.
- "explanation": ONE sentence of at most {MAX_EXPLAIN} characters that states the fact from the reference text that proves the answer.
- On-screen text (question, options, explanation) uses DEVANAGARI digits and symbols (१२, ८५%, ₹१,२०० कोटी), never
  spelled-out numbers, no emoji, no English words, no quotation marks. Numbers must be in the source.
- Spoken versions: "question_tts" (the question, one or two short sentences), "options_tts" (the 4 options, each a short
  phrase read aloud; same order), "explanation_tts" (the explanation as speech). All three follow the PHONETIC RULES below.
  Do not say the option letter, the question number or "the correct answer is": the system adds them.
- "title": the video title (at most 95 characters), a catchy line such as a Maharashtra GK quiz, with the quiz word in it.
- "social_caption": 2 sentences. "seo_keywords": 8 to 12, Marathi and English.

{PHONETIC_RULES}
""".strip()


class QuizQuestion(BaseModel):
    story: int = 1
    question: str = ""
    question_tts: str = ""
    options: list[str] = Field(default_factory=list)
    options_tts: list[str] = Field(default_factory=list)
    correct: int = 0
    explanation: str = ""
    explanation_tts: str = ""
    evidence: str = ""


class Quiz(BaseModel):
    approved: bool = True
    rejection_reason: str = ""
    title: str = ""
    social_caption: str = ""
    seo_keywords: list[str] = Field(default_factory=list)
    questions: list[QuizQuestion] = Field(default_factory=list)


def build_prompt(stories: list[dict]) -> str:
    blocks = [
        f"STORY {i}\nSource URL: {s['url']}\nTitle: {s['title']}\nText:\n\"\"\"\n{s['text'][:2600]}\n\"\"\""
        for i, s in enumerate(stories, 1)
    ]
    return "REFERENCE TEXTS (the only facts you may use)\n\n" + "\n\n".join(blocks) + f"\n\nWrite the {TARGET_QUESTIONS} question quiz now."


def _clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def check_question(raw: dict, stories: list[dict]) -> dict:
    """One question or ValueError (a precise message). The correct option's number, if any, must be in ITS story."""
    n = int(raw.get("story") or 0)
    if not 1 <= n <= len(stories):
        raise ValueError(f"story must be 1 to {len(stories)}.")
    source = f"{stories[n - 1]['title']}\n{stories[n - 1]['text']}"
    question = words_to_digits(_clean(raw.get("question")))
    options = [words_to_digits(_clean(o)) for o in raw.get("options") or []]
    explanation = words_to_digits(_clean(raw.get("explanation")))
    if not 10 <= len(question) <= MAX_QUESTION:
        raise ValueError(f"question has {len(question)} characters; it must be 10 to {MAX_QUESTION}.")
    if len(options) != 4 or len({longform.squash(o) for o in options}) != 4 or any(not o or len(o) > MAX_OPTION for o in options):
        raise ValueError(f"options must be 4 different answers of at most {MAX_OPTION} characters.")
    correct = raw.get("correct")
    if not isinstance(correct, int) or not 0 <= correct <= 3:
        raise ValueError("correct must be an index from 0 to 3.")
    if not 10 <= len(explanation) <= MAX_EXPLAIN:
        raise ValueError(f"explanation has {len(explanation)} characters; it must be 10 to {MAX_EXPLAIN}.")
    evidence = _clean(raw.get("evidence"))
    if len(evidence) < 12 or longform.squash(evidence) not in longform.squash(source):
        raise ValueError("evidence must be copied word for word from the reference text (12+ characters).")
    blocked = content_rules.blocked_in_quiz(question, *options, explanation, evidence, raw.get("question_tts"), raw.get("explanation_tts"), *(raw.get("options_tts") or []))
    if blocked:
        raise ValueError(f"'{blocked}' is not allowed in the quiz (owner rule).")
    allowed = ee.source_numbers(source)
    for number in ee.source_numbers(f"{question} {options[correct]} {explanation}"):
        if number not in allowed:
            raise ValueError(f"The number {number} is not in reference text {n}.")
    spoken = {}
    for key, text in (("question_tts", raw.get("question_tts")), ("explanation_tts", raw.get("explanation_tts"))):
        spoken[key] = ee.clean_tts_text(numbers_to_words(text))
    opts_tts = raw.get("options_tts") or []
    if len(opts_tts) != 4:
        raise ValueError("options_tts must have 4 entries.")
    # The voice reads each option from the SAME text that is shown on screen whenever that is readable as it is, so the
    # spoken option can never differ from the highlighted one; the model's phonetic version is only the fallback.
    spoken["options_tts"] = []
    for shown_raw, model_tts in zip(raw.get("options") or [], opts_tts):
        derived = ee.clean_tts_text(numbers_to_words(shown_raw)).rstrip(".")
        spoken["options_tts"].append(derived if not ee.tts_problems(derived + ".") else ee.clean_tts_text(numbers_to_words(model_tts)).rstrip("."))
    for key, value in spoken.items():
        for text in value if isinstance(value, list) else [value]:
            if not text.strip(" ."):
                raise ValueError(f"{key} is empty.")
            problems = ee.tts_problems(text)
            if problems:
                raise ValueError(f"{key}: {problems[0]}")
    banned = ee.find_forbidden(f"{question} {explanation} {spoken['question_tts']} {spoken['explanation_tts']}")
    if banned:
        raise ValueError(f"The phrase '{banned}' is banned.")
    return {"story": n, "question": question, "options": options, "correct": correct, "explanation": explanation, "evidence": evidence, **spoken}


def validate_quiz(data: dict, stories: list[dict]) -> dict:
    """A question that fails a check is dropped; the quiz needs at least MIN_QUESTIONS good ones, else the model repairs."""
    if not data.get("approved", True):
        raise ContentRejected(str(data.get("rejection_reason") or "Not approved by the editorial model."))
    good, errors = [], []
    for i, raw in enumerate(data.get("questions") or [], 1):
        try:
            good.append(check_question(raw, stories))
        except (ValueError, TypeError) as exc:
            errors.append(f"Question {i}: {exc}")
    if len(good) < MIN_QUESTIONS:
        raise ValueError(f"Only {len(good)} valid questions (need {MIN_QUESTIONS}+). " + " | ".join(errors[:4]))
    title = ee.polish_title(_clean(data.get("title")))
    if not 15 <= len(title) <= 95:
        raise ValueError(f"title has {len(title)} characters; it must be 15 to 95.")
    return {
        "title": title,
        "social_caption": _clean(data.get("social_caption"))[:400],
        "seo_keywords": ee.clean_keywords(data.get("seo_keywords", [])),
        "questions": good[:TARGET_QUESTIONS],
    }


def write_quiz(stories: list[dict]) -> dict:
    """Write the quiz, then let an independent checker answer every question blind; only confirmed questions stay."""
    for attempt in (1, 2):
        quiz = generate_json(
            system_instruction=QUIZ_INSTRUCTION,
            prompt=build_prompt(stories),
            response_model=Quiz,
            validate=lambda d: validate_quiz(d, stories),
        )
        kept, dropped = factcheck.verify_questions(quiz["questions"], stories)
        for line in dropped:
            print(f"🔎 {line}")
        if len(kept) >= MIN_QUESTIONS:
            quiz["questions"] = kept[:TARGET_QUESTIONS]
            break
        print(f"⚠️ Only {len(kept)} questions survived the answer check (attempt {attempt}).")
    else:
        raise ContentFailed(f"Fewer than {MIN_QUESTIONS} quiz questions passed the independent answer check. Run it again.")
    quiz["sources"] = [s["url"] for s in stories]
    quiz["credit_urls"] = [u for s in stories for u in s.get("urls", [s["url"]])]
    return quiz


# ----- scenes ------------------------------------------------------------------------------------


def build_scenes(quiz: dict) -> tuple[list[dict], list[float]]:
    """Intro, (question, answer) per question, closing. Returns the scene dicts and the silent seconds after each voice."""
    questions = quiz["questions"]
    total = len(questions)
    scenes = [{
        "kind": "quiz_intro",
        "headline": "आजची क्विझ",
        "subtitle": f"{total} प्रश्न • तुमचे किती बरोबर?",
        "tts_text": longform.speakable(f"आजची क्विझ. {total} प्रश्न, प्रत्येक प्रश्नासाठी पाच सेकंद. तुमचे किती उत्तरे बरोबर येतात ते पाहा."),
        "items": [],
    }]
    extras = [0.0]
    for i, q in enumerate(questions, 1):
        head = longform.speakable(f"प्रश्न क्रमांक {i}. {q['question_tts']}")
        pieces = [longform.speakable(f"{SPOKEN_LETTERS[k]}, {q['options_tts'][k]}.") for k in range(4)]
        starts, cursor = [], len(head.split())
        for piece in pieces:  # word position of each option letter in the spoken text: the card appears on that word
            starts.append(cursor)
            cursor += len(piece.split())
        common = {"q_index": i, "total": total, "correct": q["correct"], "headline": q["question"]}
        scenes.append({**common, "kind": "question", "subtitle": "", "tts_text": " ".join([head, *pieces]),
                       "items": [{"label": q["options"][k], "value": LETTERS[k], "cue_index": starts[k]} for k in range(4)]})
        extras.append(COUNTDOWN_SECONDS)
        said = longform.speakable(f"बरोबर उत्तर, {SPOKEN_LETTERS[q['correct']]}, {q['options_tts'][q['correct']]}.")
        scenes.append({**common, "kind": "answer", "subtitle": q["explanation"],
                       "tts_text": f"{said} {longform.speakable(q['explanation_tts'])}",
                       "reveal_index": 2, "explain_index": len(said.split()),
                       "items": [{"label": q["options"][k], "value": LETTERS[k]} for k in range(4)]})
        extras.append(0.0)
    scenes.append({
        "kind": "quiz_end",
        "headline": "तुम्हाला किती गुण मिळाले?",
        "subtitle": f"{total} पैकी तुमचा स्कोअर कमेंटमध्ये सांगा",
        "tts_text": longform.speakable(f"क्विझ संपली. {total} पैकी तुम्हाला किती गुण मिळाले, ते कमेंटमध्ये सांगा. उद्या नवीन विषयांवर नवी क्विझ घेऊन पुन्हा भेटू."),
        "items": [],
    })
    extras.append(0.0)
    return scenes, extras


def build_description(quiz: dict, props: dict) -> str:
    labels = []
    for s in props["scenes"]:
        labels.append("आजची क्विझ" if s["kind"] == "quiz_intro" else f"प्रश्न {s['q_index']}" if s["kind"] in ("question", "answer") else "तुमचा स्कोअर")
    marks = [(t, label) for t, label in longform.chapters(props, labels)]
    lines = [quiz["social_caption"] or quiz["title"], ""]
    if marks:
        lines += ["⏱️ प्रश्न (Chapters)", *[f"{longform.timestamp(t)} {label}" for t, label in marks], ""]
    credit = wiki_sources.credit_line(quiz.get("credit_urls") or [])
    lines += ["💬 तुम्हाला किती गुण मिळाले? कमेंटमध्ये सांगा!", "", *([credit, ""] if credit else []),
              youtube_upload.AI_NOTE, "", "🔔 MahaSpark ला फॉलो आणि सबस्क्राईब करा, रोज नवी क्विझ मिळवा.", "▶️ @MahaSparkOfficial", "", CHANNEL_HASHTAGS]
    return "\n".join(lines)


def build_tags(quiz: dict) -> list[str]:
    return youtube_upload.clean_tags(["MahaSpark", "मराठी क्विझ", "Marathi Quiz", "GK Quiz", "Maharashtra GK", "Daily Quiz", *quiz["seo_keywords"]])


# ----- run ---------------------------------------------------------------------------------------


def gather_stories(known: set[str], deadline: float) -> list[dict]:
    """Reference texts for one quiz: MH_TOPICS Maharashtra topics (different categories) and GK_TOPICS general ones."""
    stories = []
    for group, want in (("mh", MH_TOPICS), ("gk", GK_TOPICS)):
        got = 0
        for _g, _category, en_title in topic_bank.pick(group, known):
            if got >= want or time.time() > deadline:
                break
            ref = wiki_sources.fetch_topic(en_title)
            if not ref or len(ref["text"]) < MIN_STORY_CHARS:
                continue
            got += 1
            stories.append({"title": ref["title"], "url": wiki_sources.page_url("en", en_title), "urls": ref["urls"], "text": ref["text"]})
            print(f"📚 {len(stories)}/{MH_TOPICS + GK_TOPICS}: {ref['title'][:70]}")
    return stories


def finish(quiz: dict, queue, skip_render: bool, skip_upload: bool, skip_telegram: bool) -> int:
    """Voice, render, upload and announce a quiz dict (written by the model OR approved by you from a .txt)."""
    try:
        scenes, extras = build_scenes(quiz)
        scenes = longform.voice_all(scenes, extras)
    except (LLMUnavailableError, ContentFailed, ContentRejected) as exc:
        print(f"❌ {exc}")
        return 1
    props = longform.assemble("quiz", quiz["title"], scenes, ee.pick_hue(quiz["title"]), "upbeat")
    longform.write_props(props)
    print(f"🧾 {props['total_seconds']:.0f} s")
    if skip_render:
        return 0
    try:
        longform.render()
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1

    video_url, uploaded, fail_reason = None, False, ""
    if not skip_upload:
        try:
            video_url = youtube_upload.upload_video(LONG_PATH, quiz["title"], build_description(quiz, props), build_tags(quiz))
            uploaded = True
            print(f"▶️ Uploaded: {video_url}")
            thumb = longform.render_thumbnail("quiz", quiz["questions"][0]["question"], QUIZ_THUMB_TAG, "", props["bg_hue"])
            if thumb:
                try:
                    youtube_upload.set_thumbnail(video_url, thumb)
                except Exception as exc:  # noqa: BLE001
                    print(f"⚠️ Thumbnail upload failed: {exc}")
        except youtube_upload.YouTubeUnavailable as exc:
            print(f"⏭️ YouTube upload skipped: {exc}")
            fail_reason = str(exc)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ YouTube upload failed: {exc}")
            fail_reason = str(exc)

    if not uploaded and not skip_upload:
        manual_kit.deliver("क्विझ", LONG_PATH, quiz["title"], build_description(quiz, props), build_tags(quiz), fail_reason or "YouTube is not set up", send=not skip_telegram)

    if not skip_telegram:
        text = f"❓ <b>MahaSpark क्विझ: {quiz['title']}</b>\n" + (video_url or "(YouTube अपलोड झाला नाही; व्हिडिओ out/ फोल्डरमध्ये आहे.)")
        try:
            send_telegram.send_message(text)
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ Telegram notification failed: {exc}")
    if queue is not None and (uploaded or skip_upload):
        try:
            queue.record_longform("quiz", quiz["title"], "\n".join(quiz.get("sources", [])), video_url or "")
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ Could not record the quiz in the Sheet: {exc}")
    try:
        youtube_upload.credentials()
        configured = True
    except youtube_upload.YouTubeUnavailable:
        configured = False
    return 0 if (uploaded or skip_upload or not configured) else 1


def _connect_log():
    from sheet_queue import SheetQueue

    try:
        queue = SheetQueue.connect()
        return queue, queue.longform_known_keys()
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Long-video log unavailable, continuing without de-duplication: {exc}")
        return None, set()


def draft_main(argv: list[str]) -> int:
    """Write the 10 questions to drafts/quiz-<time>.txt for you to edit (a general-knowledge/Maharashtra quiz, or your own --topic)."""
    parser = argparse.ArgumentParser(prog="quiz.py draft", description="Write the quiz questions as a .txt for approval.")
    parser.add_argument("--topic", help="quiz on this topic (Wikipedia is read first) instead of the automatic topics")
    parser.add_argument("--url", action="append", default=[], help="a source article for --topic (repeat for more)")
    args = parser.parse_args(argv)
    args.topic = (args.topic or "").strip()
    args.url = [u for u in args.url if u]
    try:
        if args.topic:
            text, urls = drafts.topic_sources(args.topic, args.url, limit=MAX_STORIES)
            stories = [{"title": args.topic, "url": urls[0] if urls else "", "urls": urls, "text": text}] if len(text) >= MIN_STORY_CHARS else []
        else:
            stories = gather_stories(_connect_log()[1], time.time() + 900)
        if not stories or (not args.topic and len(stories) < 3):
            print("❌ Not enough reference text for a quiz. Add article links with --topic and --url.")
            return 1
        quiz_data = write_quiz(stories)
    except (LLMUnavailableError, ContentFailed, ContentRejected, ValueError) as exc:
        print(f"❌ {exc}")
        return 1
    path = drafts.new_draft_path("quiz")
    path.write_text(drafts.quiz_to_text(quiz_data, quiz_data["sources"]), encoding="utf-8")
    print(f"📝 Questions ready: {path}")
    drafts.announce("quiz", path, quiz_data["title"])
    return 0


def produce_main(argv: list[str]) -> int:
    """Produce the video from an approved (or self-written) questions .txt."""
    parser = argparse.ArgumentParser(prog="quiz.py produce", description="Make the quiz video from an approved questions file.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--skip-telegram", action="store_true")
    args = parser.parse_args(argv)
    try:
        quiz_data = drafts.parse_quiz(args.file.read_text(encoding="utf-8"))
    except drafts.DraftError as exc:
        print("❌ Fix these lines in the file and run again:\n" + "\n".join(f"  • {p}" for p in exc.problems))
        return 1
    print(f"✅ Questions accepted: {quiz_data['title']} ({len(quiz_data['questions'])} questions)")
    for n, q in enumerate(quiz_data["questions"], 1):
        hit = content_rules.blocked_in_quiz(q["question"], *q["options"], q["explanation"])
        if hit:
            print(f"⚠️ Q{n} mentions '{hit}', which the automatic quiz never uses. Kept because you approved the file.")
    return finish(quiz_data, _connect_log()[0], args.skip_render, args.skip_upload, args.skip_telegram)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "draft":
        return draft_main(argv[1:])
    if argv and argv[0] == "produce":
        return produce_main(argv[1:])

    parser = argparse.ArgumentParser(description="Build and publish the MahaSpark daily GK / Maharashtra quiz (automatic; use 'draft' / 'produce' for approval).")
    parser.add_argument("--auto", action="store_true", help="publish WITHOUT your approval (not recommended)")
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--skip-telegram", action="store_true")
    args = parser.parse_args(argv)
    if not args.auto:
        print("ℹ️ No video is made without your approval: writing the script for you to check (use --auto to skip this).")
        return draft_main([])

    queue, known = _connect_log()
    try:
        stories = gather_stories(known, time.time() + 900)
        if len(stories) < 3:
            print(f"❌ Only {len(stories)} readable stories; a quiz needs at least 3.")
            return 1
        quiz_data = write_quiz(stories)
        print(f"🧠 Quiz: {quiz_data['title']} ({len(quiz_data['questions'])} questions)")
    except (LLMUnavailableError, ContentFailed, ContentRejected) as exc:
        print(f"❌ {exc}")
        return 1
    return finish(quiz_data, queue, args.skip_render, args.skip_upload, args.skip_telegram)


if __name__ == "__main__":
    sys.exit(main())
