"""Detect the language of one message and keep the reply in that language."""

import re

SCRIPTS = (
    ("punjabi", 0x0A00, 0x0A7F),
    ("hindi", 0x0900, 0x097F),
    ("bengali", 0x0980, 0x09FF),
    ("gujarati", 0x0A80, 0x0AFF),
    ("odia", 0x0B00, 0x0B7F),
    ("tamil", 0x0B80, 0x0BFF),
    ("telugu", 0x0C00, 0x0C7F),
    ("kannada", 0x0C80, 0x0CFF),
    ("malayalam", 0x0D00, 0x0D7F),
    ("urdu", 0x0600, 0x06FF),
)

HINGLISH = {
    "hai",
    "hain",
    "nahi",
    "nahin",
    "kya",
    "kyun",
    "kyu",
    "kaise",
    "kese",
    "karo",
    "karna",
    "mujhe",
    "mera",
    "meri",
    "mere",
    "aap",
    "chahiye",
    "zaroorat",
    "zarurat",
    "mahine",
    "mahina",
    "paise",
    "paisa",
    "hoon",
    "hun",
    "yaar",
    "bhai",
    "batao",
    "sakte",
    "sakta",
    "sakti",
    "jaye",
    "taaki",
    "lekin",
    "kyunki",
    "bilkul",
}

PUNJABI_ROMAN = {
    "tusi",
    "tuhanu",
    "tuhada",
    "mainu",
    "kiddan",
    "sanu",
    "vich",
    "layi",
    "kujh",
    "daso",
    "dasso",
    "ohna",
}

NAMES = {
    "english": "English",
    "hindi": "Hindi in Devanagari",
    "hinglish": "Hinglish, which is Hindi written in Roman letters",
    "punjabi": "Punjabi in Gurmukhi",
    "punjabi_roman": "Punjabi written in Roman letters",
    "bengali": "Bengali",
    "gujarati": "Gujarati",
    "odia": "Odia",
    "tamil": "Tamil",
    "telugu": "Telugu",
    "kannada": "Kannada",
    "malayalam": "Malayalam",
    "urdu": "Urdu",
}

BUTTONS = {
    "english": ("Yes, fill the screen", "Not now", "Proceed"),
    "hindi": ("हाँ, स्क्रीन भरें", "अभी नहीं", "आगे बढ़ें"),
    "hinglish": ("Haan, screen bharo", "Abhi nahi", "Proceed"),
    "punjabi": ("ਹਾਂ, ਸਕਰੀਨ ਭਰੋ", "ਹੁਣ ਨਹੀਂ", "ਅੱਗੇ ਵਧੋ"),
    "punjabi_roman": ("Haan, screen bharo", "Hun nahi", "Proceed"),
}


def detect_language(text):
    """Return a language code from the script or from Roman-script words."""
    raw = text or ""
    counts = {}
    for name, start, end in SCRIPTS:
        counts[name] = sum(1 for char in raw if start <= ord(char) <= end)
    best = max(counts, key=counts.get)
    if counts[best] > 0:
        return best
    words = re.findall(r"[a-z']+", raw.lower())
    punjabi = sum(1 for word in words if word in PUNJABI_ROMAN)
    hinglish = sum(1 for word in words if word in HINGLISH)
    if punjabi and punjabi >= hinglish:
        return "punjabi_roman"
    if hinglish:
        return "hinglish"
    return "english"


def reply_instruction(language):
    name = NAMES.get(language, "English")
    return (
        "The user wrote in " + name + ". "
        "Reply only in " + name + ". "
        "Do not switch to another language. "
        "Keep the words SIP, UPI, and autopay unchanged."
    )


def button_labels(language):
    return BUTTONS.get(language) or BUTTONS["english"]


SAFETY = {
    "english": {
        "decline": (
            "I can't suggest funds or stocks, or say what to buy, sell or when. "
            "That needs a registered adviser. I can help with SIP instalments, "
            "SIP controls, what SIP terms mean, and the published figures for the "
            "SIP schemes in these notes. Want to try one of those?"
        ),
        "fallback": (
            "I'm not sure, and I don't want to guess. "
            "Here's the official source, or I can pass this to support."
        ),
        "fallback_source": (
            "I'm not sure about this one, and I don't want to guess. "
            "You can check {title}{url}, or I can pass this to support."
        ),
        "no_headlines": (
            "I couldn't find a recent headline for that, so I don't want to guess. "
            "You can try the scheme name, or ask about the SIP instalment."
        ),
        "mask": "Please don't share account numbers, PAN or phone numbers here. I've hidden it.",
    },
    "hindi": {
        "decline": (
            "मैं कोई फ़ंड या स्टॉक सुझा नहीं सकता, और यह नहीं कह सकता कि क्या खरीदें, बेचें या कब। "
            "इसके लिए रजिस्टर्ड सलाहकार चाहिए। मैं SIP किस्त, SIP कंट्रोल, SIP शब्दों और "
            "इन नोट्स में छपी योजनाओं के आंकड़ों में मदद कर सकता हूँ।"
        ),
        "fallback": "मुझे इसमें पक्का यकीन नहीं है, इसलिए मैं अनुमान नहीं लगाना चाहता। मैं इसे सपोर्ट को भेज सकता हूँ।",
        "fallback_source": "मुझे इसमें पक्का यकीन नहीं है। आप {title}{url} देख सकते हैं, या मैं इसे सपोर्ट को भेज सकता हूँ।",
        "no_headlines": "इस पर हाल की खबर नहीं मिली, इसलिए मैं अनुमान नहीं लगाऊँगा। योजना का नाम लिखें, या SIP किस्त के बारे में पूछें।",
        "mask": "कृपया खाता नंबर, PAN या फ़ोन नंबर यहाँ न लिखें। मैंने इसे छिपा दिया है।",
    },
    "hinglish": {
        "decline": (
            "Main koi fund ya stock suggest nahi kar sakta, aur yeh nahi keh sakta ki kya kharidein, "
            "bechein ya kab. Iske liye registered adviser chahiye. Main SIP instalment, SIP controls, "
            "SIP words, aur in notes ke published figures mein madad kar sakta hoon."
        ),
        "fallback": "Mujhe isme pakka yakeen nahi hai, isliye main guess nahi karna chahta. Main ise support ko bhej sakta hoon.",
        "fallback_source": "Mujhe isme pakka yakeen nahi hai. Aap {title}{url} dekh sakte hain, ya main ise support ko bhej sakta hoon.",
        "no_headlines": "Is par recent khabar nahi mili, isliye main guess nahi karunga. Scheme ka naam likhein, ya SIP instalment ke baare mein poochhein.",
        "mask": "Please account number, PAN ya phone number yahan mat likhein. Maine ise chhupa diya hai.",
    },
    "punjabi": {
        "decline": (
            "ਮੈਂ ਕੋਈ ਫੰਡ ਜਾਂ ਸਟਾਕ ਸੁਝਾ ਨਹੀਂ ਸਕਦਾ, ਅਤੇ ਇਹ ਨਹੀਂ ਕਹਿ ਸਕਦਾ ਕਿ ਕੀ ਖਰੀਦੋ, ਵੇਚੋ ਜਾਂ ਕਦੋਂ। "
            "ਇਸ ਲਈ ਰਜਿਸਟਰਡ ਸਲਾਹਕਾਰ ਚਾਹੀਦਾ ਹੈ। ਮੈਂ SIP ਕਿਸ਼ਤ, SIP ਕੰਟਰੋਲ ਅਤੇ ਛਪੇ ਅੰਕੜਿਆਂ ਵਿੱਚ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ।"
        ),
        "fallback": "ਮੈਨੂੰ ਇਸ ਬਾਰੇ ਪੱਕਾ ਯਕੀਨ ਨਹੀਂ, ਇਸ ਲਈ ਮੈਂ ਅੰਦਾਜ਼ਾ ਨਹੀਂ ਲਗਾਵਾਂਗਾ।",
        "fallback_source": "ਮੈਨੂੰ ਇਸ ਬਾਰੇ ਪੱਕਾ ਯਕੀਨ ਨਹੀਂ। ਤੁਸੀਂ {title}{url} ਵੇਖ ਸਕਦੇ ਹੋ।",
        "no_headlines": "ਇਸ ਬਾਰੇ ਤਾਜ਼ਾ ਖ਼ਬਰ ਨਹੀਂ ਮਿਲੀ, ਇਸ ਲਈ ਮੈਂ ਅੰਦਾਜ਼ਾ ਨਹੀਂ ਲਗਾਵਾਂਗਾ।",
        "mask": "ਕਿਰਪਾ ਕਰਕੇ ਖਾਤਾ ਨੰਬਰ, PAN ਜਾਂ ਫ਼ੋਨ ਨੰਬਰ ਇੱਥੇ ਨਾ ਲਿਖੋ। ਮੈਂ ਇਹ ਲੁਕਾ ਦਿੱਤਾ ਹੈ।",
    },
    "punjabi_roman": {
        "decline": (
            "Main koi fund ja stock suggest nahi kar sakda, te eh nahi keh sakda ki ki kharido, "
            "vecho ja kadon. Is layi registered adviser chahida. Main SIP instalment, SIP controls "
            "te published figures vich madad kar sakda haan."
        ),
        "fallback": "Mainu eh pakka nahi pata, is layi main andaza nahi lavanga.",
        "fallback_source": "Mainu eh pakka nahi pata. Tusi {title}{url} vekh sakde ho.",
        "no_headlines": "Is baare taza khabar nahi mili, is layi main andaza nahi lavanga.",
        "mask": "Account number, PAN ja phone number ethe na likho. Main eh luka ditta hai.",
    },
}


def safety_text(language, key, **kwargs):
    table = SAFETY.get(language) or SAFETY["english"]
    return table[key].format(**kwargs)
