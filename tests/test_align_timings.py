import align_timings as at
from helpers import valid_story


def story_with_scenes():
    story = valid_story()
    story["tts_narration_script"] = " ".join(s["tts_text"] for s in story["scenes"])
    return story


def test_perfect_whisper_match_uses_exact_times():
    words = ["आज", "पुणे", "शहरात", "मेट्रो", "सुरू", "झाली."]
    heard = [at.TimedWord(w, i * 0.5, i * 0.5 + 0.4) for i, w in enumerate(words)]
    timed, matched = at.align_script_to_audio(words, heard, duration=3.2)
    assert matched == 1.0
    assert [round(t.start, 2) for t in timed] == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]


def test_misspelled_whisper_words_still_align_by_similarity():
    script = ["महापालिकेने", "मंजुरी", "दिली."]
    heard = [at.TimedWord("महापालिकेन", 0.2, 0.9), at.TimedWord("मंजूरी", 1.0, 1.6), at.TimedWord("दिली", 1.7, 2.0)]
    timed, matched = at.align_script_to_audio(script, heard, duration=2.2)
    assert matched == 1.0
    assert timed[1].start == 1.0


def test_unmatched_words_are_interpolated_in_order():
    script = ["एक", "दोन", "तीन", "चार"]
    heard = [at.TimedWord("एक", 0.0, 0.5), at.TimedWord("चार", 3.0, 3.5)]
    timed, _ = at.align_script_to_audio(script, heard, duration=4.0)
    starts = [t.start for t in timed]
    assert starts == sorted(starts)
    assert 0.5 <= timed[1].start < timed[2].start < 3.0


def test_no_whisper_output_falls_back_to_proportional_timing():
    script = ["एक", "दोन", "तीन"]
    timed, matched = at.align_script_to_audio(script, [], duration=3.0)
    assert matched == 0.0
    assert timed[0].start == 0.0 and timed[-1].end <= 3.0
    assert all(a.end <= b.start + 1e-6 for a, b in zip(timed, timed[1:]))


def test_story_timings_add_words_scenes_and_duration():
    story = story_with_scenes()
    result = at.build_story_timings(story, [], duration=20.0)
    assert result["duration_seconds"] == 20.0
    assert len(result["words"]) == len(story["tts_narration_script"].split())
    assert result["scenes"][0]["start"] == 0.0
    assert result["scenes"][-1]["end"] == 20.0
    starts = [s["start"] for s in result["scenes"]]
    assert starts == sorted(starts)
    assert {w["scene"] for w in result["words"]} == {0, 1, 2, 3}
    # each scene starts exactly where its first word starts (except scene 0, pinned to 0)
    first_word_of_scene_2 = next(w for w in result["words"] if w["scene"] == 2)
    assert result["scenes"][2]["start"] == first_word_of_scene_2["start"]


def test_mismatched_scene_text_refuses_to_align():
    story = story_with_scenes()
    story["tts_narration_script"] += " अतिरिक्त"
    try:
        at.build_story_timings(story, [], 10.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_voiceless_story_is_timed_from_the_script_and_marked_silent(tmp_path):
    import json

    story = story_with_scenes()
    path = tmp_path / "story.json"
    path.write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
    result = at.main_voiceless(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert result["audio"] is False and saved["audio"] is False
    assert saved["duration_seconds"] == at.estimate_duration(story["tts_narration_script"])
    assert len(saved["words"]) == len(story["tts_narration_script"].split())
    assert saved["scenes"][-1]["end"] == saved["duration_seconds"]


def test_estimated_duration_has_a_floor_and_grows_with_length():
    assert at.estimate_duration("एक.") == at.MIN_VOICELESS_SECONDS
    long_script = " ".join(["शब्द,"] * 120) + "."
    assert at.estimate_duration(long_script) > 50


def test_audio_is_loaded_as_16k_mono_float_array_without_av(tmp_path):
    import wave

    import numpy as np

    path = tmp_path / "v.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes((np.sin(np.linspace(0, 200, 24000)) * 12000).astype("<i2").tobytes())  # 1 second
    audio = at.load_audio_16k(path)
    assert audio.dtype == np.float32 and abs(len(audio) - 16000) <= 1
    assert 0.2 < float(np.abs(audio).max()) <= 1.0
