"""Topic bank for the evergreen explainer and the daily general-knowledge quiz (not daily news).

Each entry is (group, category, English Wikipedia title). ``mh`` = about Maharashtra, ``gk`` = India / world / science.
Titles go through ``wiki_sources.fetch_topic``, which follows redirects and falls back to a search, so a slightly
wrong title still finds its article. Add topics freely: one line each.
"""

from __future__ import annotations

import content_rules
import random
from datetime import date

BANK: list[tuple[str, str, str]] = [
    # Maharashtra: geography and nature
    *[("mh", "भूगोल", t) for t in (
        "Maharashtra", "Western Ghats", "Konkan", "Godavari", "Krishna River", "Bhima River", "Tapti River", "Lonar Lake",
        "Tadoba Andhari Tiger Reserve", "Sanjay Gandhi National Park", "Mahabaleshwar", "Kaas Plateau", "Deccan Plateau",
        "Ratnagiri", "Nashik", "Kolhapur", "Nagpur", "Pune", "Mumbai", "Satara", "Vidarbha", "Marathwada", "Khandesh")],
    # Maharashtra: forts, temples, monuments
    *[("mh", "किल्ले व वारसा", t) for t in (
        "Raigad Fort", "Sinhagad", "Pratapgad", "Shivneri", "Rajgad Fort", "Purandar Fort", "Daulatabad Fort", "Sindhudurg Fort",
        "Ajanta Caves", "Ellora Caves", "Elephanta Caves", "Gateway of India", "Chhatrapati Shivaji Maharaj Terminus",
        "Shaniwar Wada", "Bibi Ka Maqbara", "Lohagad")],
    *[("mh", "मंदिरे व तीर्थक्षेत्रे", t) for t in (
        "Pandharpur", "Bhimashankar Temple", "Trimbakeshwar Shiva Temple", "Grishneshwar Temple", "Siddhivinayak Temple, Mumbai",
        "Shirdi Sai Baba", "Tuljabhavani Temple", "Mahalakshmi Temple, Kolhapur", "Jejuri", "Ashtavinayak")],
    # Maharashtra: history and personalities
    *[("mh", "इतिहास", t) for t in (
        "Shivaji", "Sambhaji", "Maratha Empire", "Peshwa", "Baji Rao I", "Third Battle of Panipat", "Tarabai", "Ahilyabai Holkar",
        "Shahu of Kolhapur", "Samyukta Maharashtra Movement", "Battle of Sinhagad", "Rajaram I")],
    *[("mh", "थोर व्यक्ती", t) for t in (
        "Jyotirao Phule", "Savitribai Phule", "Bal Gangadhar Tilak", "Gopal Krishna Gokhale", "B. R. Ambedkar", "Vinoba Bhave",
        "Dnyaneshwar", "Tukaram", "Eknath", "Namdev", "Samarth Ramdas", "Dhondo Keshav Karve", "Vasudev Balwant Phadke",
        "Anna Hazare", "Lata Mangeshkar", "P. L. Deshpande", "Sant Gadge Baba")],
    # Maharashtra: culture, food, language
    *[("mh", "संस्कृती", t) for t in (
        "Ganesh Chaturthi", "Gudi Padwa", "Pandharpur Wari", "Lavani", "Warli painting", "Paithani", "Vada pav", "Puran poli",
        "Marathi language", "Marathi literature", "Tamasha (Marathi)", "Dahi Handi", "Kolhapuri chappal", "Alphonso mango",
        "Marathi cinema", "Marathi theatre", "Natyasangeet")],
    # Maharashtra: institutions and economy
    *[("mh", "संस्था व अर्थव्यवस्था", t) for t in (
        "Reserve Bank of India", "Bombay Stock Exchange", "National Stock Exchange of India", "Bombay High Court",
        "Maharashtra Legislative Assembly", "Mumbai Suburban Railway", "Mumbai Metro", "Jawaharlal Nehru Port",
        "Tata Institute of Fundamental Research", "Indian Institute of Technology Bombay", "Fergusson College", "Bhabha Atomic Research Centre")],
    # India and world: civics
    *[("gk", "नागरिकशास्त्र", t) for t in (
        "Constitution of India", "Fundamental rights in India", "Panchayati raj in India", "Right to Information Act, 2005",
        "Goods and Services Tax (India)", "Unified Payments Interface", "Aadhaar", "Election Commission of India", "Lok Sabha",
        "Rajya Sabha", "Supreme Court of India", "President of India", "Indian rupee", "Census of India")],
    # India and world: science and technology
    *[("gk", "विज्ञान", t) for t in (
        "Photosynthesis", "Solar System", "Monsoon", "Human digestive system", "DNA", "Vaccine", "Electricity", "Climate change",
        "Black hole", "Chandrayaan-3", "Mars Orbiter Mission", "Periodic table", "Gravity", "Water cycle", "Earthquake",
        "Cyclone", "Internet", "Artificial intelligence", "Blood type", "Indian Space Research Organisation", "Vikram Sarabhai",
        "A. P. J. Abdul Kalam", "Homi J. Bhabha", "Jagadish Chandra Bose", "C. V. Raman")],
    # India and world: history and geography
    *[("gk", "भारत", t) for t in (
        "Taj Mahal", "Mahatma Gandhi", "Jawaharlal Nehru", "Sardar Vallabhbhai Patel", "Indian independence movement", "Ganges",
        "Himalayas", "Thar Desert", "Quit India Movement", "Dandi March", "Jallianwala Bagh massacre", "Red Fort",
        "Konark Sun Temple", "Kerala", "Rajasthan", "Indian Railways", "Sundarbans", "Kaziranga National Park")],
    # India and world: sports
    *[("gk", "क्रीडा", t) for t in (
        "Sachin Tendulkar", "Sunil Gavaskar", "Kabaddi", "Kho kho", "Indian Premier League", "Mumbai Indians", "Neeraj Chopra",
        "Khashaba Jadhav", "1983 Cricket World Cup", "Olympic Games", "Mary Kom", "P. V. Sindhu", "Mahendra Singh Dhoni")],
]


def wiki_key(title: str) -> str:
    from wiki_sources import page_url

    return page_url("en", title).lower()


def ordered(group: str | None = None, today: date | None = None, bank: list | None = None) -> list[tuple[str, str, str]]:
    """The topics of ``group`` (or all) in a repeatable order that changes every day: categories take turns, so two
    videos on the same day (or on consecutive days) are never from the same category."""
    today = today or date.today()
    rng = random.Random(today.toordinal())
    by_cat: dict[str, list] = {}
    for entry in bank if bank is not None else BANK:
        if group is None or entry[0] == group:
            by_cat.setdefault(entry[1], []).append(entry)
    cats = sorted(by_cat)
    rng.shuffle(cats)
    for items in by_cat.values():
        rng.shuffle(items)
    out = []
    for i in range(max((len(v) for v in by_cat.values()), default=0)):
        for cat in cats:
            if i < len(by_cat[cat]):
                out.append(by_cat[cat][i])
    return out


def pick(group: str | None, known: set[str], today: date | None = None, bank: list | None = None):
    """Yield unused topics (not in ``known``, a set of lower-cased Wikipedia urls) in today's order."""
    for entry in ordered(group, today, bank):
        if content_rules.blocked_topic(entry[2]):  # owner rule: never Savarkar, the RSS or Godse
            continue
        if wiki_key(entry[2]) not in known:
            yield entry
