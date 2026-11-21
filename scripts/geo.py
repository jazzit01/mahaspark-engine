"""Where a topic is: a small gazetteer of Maharashtra places for the animated map on the explainer's title scene.

Keys are the lower-cased English Wikipedia titles of ``topic_bank`` (and ``wiki_key`` URLs end with them). A topic that
is not listed here (people, festivals, science ...) simply gets no map. Coordinates are approximate (map pin level).
"""

from __future__ import annotations

from urllib.parse import unquote

# title -> (latitude, longitude, Marathi label)
PLACES: dict[str, tuple[float, float, str]] = {
    "mumbai": (18.97, 72.82, "मुंबई"),
    "pune": (18.52, 73.86, "पुणे"),
    "nagpur": (21.15, 79.09, "नागपूर"),
    "nashik": (20.00, 73.79, "नाशिक"),
    "kolhapur": (16.70, 74.24, "कोल्हापूर"),
    "satara": (17.68, 74.02, "सातारा"),
    "ratnagiri": (16.99, 73.30, "रत्नागिरी"),
    "mahabaleshwar": (17.92, 73.66, "महाबळेश्वर"),
    "kaas plateau": (17.72, 73.82, "कास पठार"),
    "lonar lake": (19.98, 76.51, "लोणार"),
    "tadoba andhari tiger reserve": (20.25, 79.42, "ताडोबा"),
    "sanjay gandhi national park": (19.21, 72.91, "संजय गांधी उद्यान"),
    "konkan": (17.30, 73.40, "कोकण"),
    "vidarbha": (20.90, 78.60, "विदर्भ"),
    "marathwada": (19.20, 76.60, "मराठवाडा"),
    "khandesh": (21.00, 75.30, "खानदेश"),
    "raigad fort": (18.23, 73.44, "रायगड"),
    "sinhagad": (18.37, 73.76, "सिंहगड"),
    "pratapgad": (17.94, 73.58, "प्रतापगड"),
    "shivneri": (19.20, 73.86, "शिवनेरी"),
    "rajgad fort": (18.25, 73.68, "राजगड"),
    "purandar fort": (18.28, 73.98, "पुरंदर"),
    "daulatabad fort": (19.94, 75.22, "दौलताबाद"),
    "sindhudurg fort": (16.04, 73.46, "सिंधुदुर्ग"),
    "ajanta caves": (20.55, 75.70, "अजिंठा"),
    "ellora caves": (20.03, 75.18, "वेरूळ"),
    "elephanta caves": (18.96, 72.93, "घारापुरी"),
    "gateway of india": (18.92, 72.83, "गेटवे ऑफ इंडिया"),
    "chhatrapati shivaji maharaj terminus": (18.94, 72.84, "सीएसएमटी"),
    "shaniwar wada": (18.52, 73.86, "शनिवारवाडा"),
    "bibi ka maqbara": (19.90, 75.32, "बीबी का मकबरा"),
    "lohagad": (18.71, 73.48, "लोहगड"),
    "pandharpur": (17.68, 75.33, "पंढरपूर"),
    "bhimashankar temple": (19.07, 73.54, "भीमाशंकर"),
    "trimbakeshwar shiva temple": (19.93, 73.53, "त्र्यंबकेश्वर"),
    "grishneshwar temple": (20.02, 75.17, "घृष्णेश्वर"),
    "siddhivinayak temple, mumbai": (19.02, 72.83, "सिद्धिविनायक"),
    "shirdi sai baba": (19.77, 74.48, "शिर्डी"),
    "tuljabhavani temple": (18.01, 76.07, "तुळजापूर"),
    "mahalakshmi temple, kolhapur": (16.70, 74.22, "कोल्हापूर"),
    "jejuri": (18.28, 74.16, "जेजुरी"),
    "godavari": (19.93, 73.53, "गोदावरी उगम"),
    "krishna river": (17.92, 73.66, "कृष्णा उगम"),
    "bhima river": (19.07, 73.54, "भीमा उगम"),
    "tapti river": (21.00, 75.50, "तापी"),
    "bombay high court": (18.93, 72.83, "मुंबई उच्च न्यायालय"),
    "bombay stock exchange": (18.93, 72.83, "बीएसई"),
    "reserve bank of india": (18.93, 72.84, "रिझर्व्ह बँक"),
    "jawaharlal nehru port": (18.95, 72.95, "जेएनपीटी"),
    "indian institute of technology bombay": (19.13, 72.92, "आयआयटी मुंबई"),
    "fergusson college": (18.52, 73.84, "फर्ग्युसन"),
    "tata institute of fundamental research": (18.91, 72.81, "टीआयएफआर"),
}


def _key(topic: str) -> str:
    """A wiki title, a wiki page URL or a bank key -> the lower-cased title used in PLACES."""
    text = unquote(str(topic or "")).strip()
    if "/wiki/" in text:
        text = text.rsplit("/wiki/", 1)[1]
    return text.replace("_", " ").strip().lower()


def pin_for(topic: str) -> dict | None:
    """``{"lat", "lon", "label"}`` for a topic in Maharashtra, or None (no map)."""
    found = PLACES.get(_key(topic))
    if not found:
        return None
    lat, lon, label = found
    return {"lat": lat, "lon": lon, "label": label}


def attach_map(props: dict, topic: str) -> dict:
    pin = pin_for(topic)
    if pin:
        props["map"] = pin
    return props
