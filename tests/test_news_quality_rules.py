import pytest

from news_writer import validate_news_pack


VALID_PACK = {
    "badge": "मोठी बातमी",
    "headline_part1": "पुण्यातील",
    "headline_part2": "सर्व्हरमध्ये तांत्रिक बिघाड, ३ जखमी!",
    "hook_pill": "महाराष्ट्रात तातडीची कारवाई",
    "bullets": [
        {"icon": "⚡", "text": "शहराच्या मुख्य सर्व्हरमध्ये रात्री १ वाजता तांत्रिक बिघाड आल्याने सेवा ठप्प झाली आणि ३ कर्मचारी जखमी झाले."},
        {"icon": "🚨", "text": "पोलिस आणि तांत्रिक पथकाने घटनास्थळी तातडीची तपासणी सुरू केली आणि इमारतीतील सुरक्षा प्रणालीची पडताळणी केली."},
    ],
    "audio_mood": "breaking",
    "visual_prompt": "Documentary press photo: Real Indian editorial news photograph, authentic Maharashtra scene, natural daylight, candid photojournalism, unedited realism, clean negative space on the left, no watermark, no text, no logo, neutral journalistic composition.",
    "yt_shorts_title": "पुण्यात सर्व्हरमध्ये मोठा तांत्रिक बिघाड",
    "yt_shorts_description": "पुण्यातील मुख्य सर्व्हरमध्ये तांत्रिक बिघाड झाल्याची माहिती समोर आली आहे. अधिक माहितीसाठी तपासणी सुरू आहे.",
    "ig_reels_caption": "Neutral Marathi news caption with headline context and key facts.",
    "ig_hashtags": "#MahaSpark #MarathiNews #Maharashtra",
}


def test_validate_news_pack_accepts_real_news_payload():
    result = validate_news_pack(VALID_PACK.copy())
    assert result["audio_mood"] == "breaking"
    assert result["badge"] == "मोठी बातमी"


def test_validate_news_pack_rejects_vague_promotional_phrases():
    invalid = VALID_PACK.copy()
    invalid["headline_part2"] = "अचानक काहीतरी घडले आणि सर्व काही बदलले!"

    with pytest.raises(ValueError, match="vague|promotional|neutral news"):
        validate_news_pack(invalid)
