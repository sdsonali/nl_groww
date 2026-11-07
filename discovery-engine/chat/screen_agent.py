"""Fill the recovery screen from what the person describes.

This does not call the model. It only changes the prototype screen.
No payment is sent.
"""

import re

from chat.language import detect_language

DEFAULT_AMOUNT = "₹2,000"
DEFAULT_BANK = "bank account ending 4821"

SCENES = [
    {
        "label": "Money already left the bank",
        "kind": "status",
        "action": "show the status",
        "hints": (
            "money left",
            "already left",
            "debited but",
            "not allotted",
            "didn't allotted",
            "didnt allotted",
            "not refund",
        ),
    },
    {
        "label": "Bank change",
        "kind": "bank",
        "action": "update the bank",
        "hints": (
            "bank change",
            "changed my bank",
            "changed the bank",
            "change my bank",
            "change the bank",
            "change of bank",
            "new bank",
            "switched my bank",
            "switched bank",
            "switch my bank",
            "different bank",
        ),
    },
    {
        "label": "UPI autopay is off before the debit day",
        "kind": "renew",
        "action": "renew autopay",
        "hints": (
            "autopay is off",
            "autopay off",
            "upi autopay",
            "never gets debited",
            "never get debited",
            "manually pay",
            "manual pay",
            "manually",
            "manual",
            "manully",
            "manualy",
            "manuall",
            "every month i have to",
            "renew autopay",
            "mandate off",
            "mandate expired",
            "upi is off",
            "setting the autopay",
            "setting autopay",
            "set the autopay",
            "set autopay",
            "setup autopay",
            "set up autopay",
            "autopay set",
            "autopay on",
            "turn autopay",
        ),
    },
    {
        "label": "Autopay did not send it",
        "kind": "pay",
        "action": "pay this instalment",
        "hints": (
            "did not send",
            "didn't send",
            "didnt send",
            "no retry",
            "remains pending",
            "still pending",
            "autopay did not",
            "auto payment fails",
        ),
    },
    {
        "label": "Bank rejected the debit",
        "kind": "pay",
        "action": "pay this instalment",
        "hints": (
            "rejected",
            "bank declined",
            "debit declined",
            "sip declined",
            "bank rejected",
        ),
    },
]

HELP_RE = re.compile(
    r"assistance|help me|help here|do it for me|fill (the |this )?screen|without using the ui",
    re.I,
)
YES_RE = re.compile(
    r"^(yes|y|yeah|yep|haan|ha|ok|okay|sure|continue|go ahead|use those|use that)\b",
    re.I,
)
NO_RE = re.compile(r"^(no|nah|nope|don't|dont|mat |stop)\b", re.I)
FINISH_RE = re.compile(r"\b(proceed|finish|complete|turn it on|turn on autopay)\b", re.I)
OTHER_RE = re.compile(
    r"\b(what is|what's|news|headline|which fund|nav|expense|khabar|samachar)\b",
    re.I,
)
BANK_RE = re.compile(r"(?:ending|account|a/c|ac)\s*(\d{4})\b", re.I)
AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr|amount|rupees)\s*(\d{3,6})\b", re.I)
BARE_AMOUNT_RE = re.compile(r"\b(\d{3,5})\b")


def _scene_by_label(label):
    for scene in SCENES:
        if scene["label"] == label:
            return scene
    return None


def classify(text):
    lowered = (text or "").lower()
    for scene in SCENES:
        if any(hint in lowered for hint in scene["hints"]):
            return scene
    return None


def _money(number):
    value = int(number)
    return "₹" + format(value, ",")


def read_details(text, amount, bank):
    found_bank = BANK_RE.search(text or "")
    if found_bank:
        bank = "bank account ending " + found_bank.group(1)
    found_amount = AMOUNT_RE.search(text or "")
    if found_amount:
        amount = _money(found_amount.group(1))
    elif not found_bank:
        bare = BARE_AMOUNT_RE.search(text or "")
        if bare:
            amount = _money(bare.group(1))
    return amount, bank


COPY = {
    "english": {
        "offer_status": (
            "It looks like the money already left your bank. "
            "There is no second payment. Want me to show that here?"
        ),
        "offer_renew": (
            "UPI autopay is your permission for the bank to send each instalment, and it looks off. "
            "I can turn it on for {amount} from the {bank}. Want me to do that?"
        ),
        "offer_pay": (
            "It looks like this instalment didn't go through. "
            "I can mark {amount} from the {bank} for this month only. "
            "Want me to do that?"
        ),
        "filled": (
            "I've filled the screen with {amount} from the {bank} and opened the confirm step. "
            "Say proceed and I'll finish it. No real payment is sent."
        ),
        "done_status": (
            "I've set the screen to: {label}. There is no pay button, so this month is not charged again."
        ),
        "done_renew": (
            "I've finished the renew step on the screen for {amount} from the {bank}. "
            "Autopay shows as on. No real debit was sent."
        ),
        "done_pay": (
            "I've finished Pay this instalment on the screen for {amount} from the {bank}. "
            "It shows as received. No real payment was sent."
        ),
        "offer_bank": (
            "It looks like the bank on this SIP changed. "
            "You can add the account holder name. It is optional. "
            "I'll fill the bank name, account number, phone number, and address as ***. Want me to do that?"
        ),
        "done_bank": (
            "I've filled the account holder, bank name, account number, phone number, and address as ***. "
            "The bank on the screen is updated. No real payment was sent."
        ),
        "done_plain": "I've updated the screen. No real payment is sent.",
        "clear": "Okay. I won't change the screen. You can still use the phone on the page.",
    },
    "hindi": {
        "offer_status": (
            "यह {label} जैसा लगता है। मैं स्क्रीन पर यही स्थिति भर सकता हूँ। "
            "पे बटन नहीं है, इसलिए दूसरा भुगतान शुरू नहीं होगा। हाँ लिखें।"
        ),
        "offer_renew": (
            "यह {label} जैसा लगता है। मैं इस स्क्रीन पर UPI autopay renew कर सकता हूँ, "
            "आपको खुद टैप नहीं करना होगा। कोई असली भुगतान नहीं जाएगा। "
            "मैं {amount} और {bank} इस्तेमाल करूँगा, जब तक आप दूसरी राशि और आखिरी 4 अंक न लिखें। "
            "हाँ लिखें, मैं confirm स्टेप भर दूँगा। proceed लिखें, मैं इसे स्क्रीन पर पूरा कर दूँगा।"
        ),
        "offer_pay": (
            "यह {label} जैसा लगता है। मैं इस स्क्रीन पर Pay this instalment खोल सकता हूँ। "
            "कोई असली भुगतान नहीं जाएगा। मैं {amount} और {bank} इस्तेमाल करूँगा, "
            "जब तक आप दूसरी राशि और आखिरी 4 अंक न लिखें। हाँ लिखें, मैं confirm स्टेप भर दूँगा।"
        ),
        "filled": (
            "मैंने स्क्रीन पर {amount} और {bank} भर दिया है और confirm स्टेप खोल दिया है। "
            "proceed लिखें, मैं इसे पूरा कर दूँगा। कोई असली भुगतान नहीं जाएगा।"
        ),
        "done_status": "मैंने स्क्रीन पर {label} लगा दिया है। पे बटन नहीं है, इसलिए इस महीने फिर से चार्ज नहीं होगा।",
        "done_renew": (
            "मैंने स्क्रीन पर renew पूरा कर दिया है, {amount}, {bank}। "
            "Autopay ऑन दिख रहा है। कोई असली डेबिट नहीं गया।"
        ),
        "done_pay": (
            "मैंने स्क्रीन पर Pay this instalment पूरा कर दिया है, {amount}, {bank}। "
            "यह received दिख रहा है। कोई असली भुगतान नहीं गया।"
        ),
        "done_plain": "मैंने स्क्रीन अपडेट कर दी है। कोई असली भुगतान नहीं गया।",
        "clear": "ठीक है। मैं स्क्रीन नहीं बदलूँगा। आप पेज पर फ़ोन का इस्तेमाल कर सकते हैं।",
    },
    "hinglish": {
        "offer_status": (
            "Yeh {label} jaisa lagta hai. Main screen par yahi status bhar sakta hoon. "
            "Pay button nahi hai, isliye doosra payment start nahi hoga. Haan likhein."
        ),
        "offer_renew": (
            "Yeh {label} jaisa lagta hai. Main is screen par UPI autopay renew kar sakta hoon, "
            "aapko khud tap nahi karna padega. Koi asli payment nahi jayegi. "
            "Main {amount} aur {bank} use karunga, jab tak aap alag amount aur last 4 digits na likhein. "
            "Haan likhein, main confirm step bhar dunga. Proceed likhein, main screen par finish kar dunga."
        ),
        "offer_pay": (
            "Yeh {label} jaisa lagta hai. Main is screen par Pay this instalment khol sakta hoon. "
            "Koi asli payment nahi jayegi. Main {amount} aur {bank} use karunga, "
            "jab tak aap alag amount aur last 4 digits na likhein. Haan likhein, main confirm step bhar dunga."
        ),
        "filled": (
            "Maine screen par {amount} aur {bank} bhar diya hai aur confirm step khol diya hai. "
            "Proceed likhein, main finish kar dunga. Koi asli payment nahi jayegi."
        ),
        "done_status": "Maine screen par {label} laga diya hai. Pay button nahi hai, is mahine dobara charge nahi hoga.",
        "done_renew": (
            "Maine screen par renew finish kar diya hai, {amount}, {bank}. "
            "Autopay on dikh raha hai. Koi asli debit nahi gayi."
        ),
        "done_pay": (
            "Maine screen par Pay this instalment finish kar diya hai, {amount}, {bank}. "
            "Yeh received dikh raha hai. Koi asli payment nahi gayi."
        ),
        "done_plain": "Maine screen update kar di hai. Koi asli payment nahi gayi.",
        "clear": "Theek hai. Main screen nahi badlunga. Aap page par phone use kar sakte hain.",
    },
    "punjabi": {
        "offer_status": (
            "ਇਹ {label} ਵਰਗਾ ਲੱਗਦਾ ਹੈ। ਮੈਂ ਸਕਰੀਨ ਉੱਤੇ ਇਹੀ ਸਥਿਤੀ ਭਰ ਸਕਦਾ ਹਾਂ। "
            "ਪੇ ਬਟਨ ਨਹੀਂ ਹੈ, ਇਸ ਲਈ ਦੂਜਾ ਭੁਗਤਾਨ ਸ਼ੁਰੂ ਨਹੀਂ ਹੋਵੇਗਾ। ਹਾਂ ਲਿਖੋ।"
        ),
        "offer_renew": (
            "ਇਹ {label} ਵਰਗਾ ਲੱਗਦਾ ਹੈ। ਮੈਂ ਇਸ ਸਕਰੀਨ ਉੱਤੇ UPI autopay renew ਕਰ ਸਕਦਾ ਹਾਂ। "
            "ਕੋਈ ਅਸਲ ਭੁਗਤਾਨ ਨਹੀਂ ਜਾਵੇਗਾ। ਮੈਂ {amount} ਅਤੇ {bank} ਵਰਤਾਂਗਾ, "
            "ਜਦ ਤੱਕ ਤੁਸੀਂ ਹੋਰ ਰਕਮ ਅਤੇ ਆਖ਼ਰੀ 4 ਅੰਕ ਨਾ ਲਿਖੋ। "
            "ਹਾਂ ਲਿਖੋ, ਮੈਂ confirm ਭਰ ਦਿਆਂਗਾ। proceed ਲਿਖੋ, ਮੈਂ ਸਕਰੀਨ ਉੱਤੇ ਪੂਰਾ ਕਰ ਦਿਆਂਗਾ।"
        ),
        "offer_pay": (
            "ਇਹ {label} ਵਰਗਾ ਲੱਗਦਾ ਹੈ। ਮੈਂ ਇਸ ਸਕਰੀਨ ਉੱਤੇ Pay this instalment ਖੋਲ੍ਹ ਸਕਦਾ ਹਾਂ। "
            "ਕੋਈ ਅਸਲ ਭੁਗਤਾਨ ਨਹੀਂ ਜਾਵੇਗਾ। ਮੈਂ {amount} ਅਤੇ {bank} ਵਰਤਾਂਗਾ। ਹਾਂ ਲਿਖੋ।"
        ),
        "filled": (
            "ਮੈਂ ਸਕਰੀਨ ਉੱਤੇ {amount} ਅਤੇ {bank} ਭਰ ਦਿੱਤਾ ਹੈ ਅਤੇ confirm ਖੋਲ੍ਹ ਦਿੱਤਾ ਹੈ। "
            "proceed ਲਿਖੋ। ਕੋਈ ਅਸਲ ਭੁਗਤਾਨ ਨਹੀਂ ਜਾਵੇਗਾ।"
        ),
        "done_status": "ਮੈਂ ਸਕਰੀਨ ਉੱਤੇ {label} ਲਾ ਦਿੱਤਾ ਹੈ। ਪੇ ਬਟਨ ਨਹੀਂ ਹੈ, ਇਸ ਮਹੀਨੇ ਫੇਰ ਚਾਰਜ ਨਹੀਂ ਹੋਵੇਗਾ।",
        "done_renew": (
            "ਮੈਂ ਸਕਰੀਨ ਉੱਤੇ renew ਪੂਰਾ ਕਰ ਦਿੱਤਾ ਹੈ, {amount}, {bank}। "
            "Autopay ਚਾਲੂ ਦਿਖ ਰਿਹਾ ਹੈ। ਕੋਈ ਅਸਲ ਡੈਬਿਟ ਨਹੀਂ ਗਈ।"
        ),
        "done_pay": (
            "ਮੈਂ ਸਕਰੀਨ ਉੱਤੇ Pay this instalment ਪੂਰਾ ਕਰ ਦਿੱਤਾ ਹੈ, {amount}, {bank}। "
            "ਇਹ received ਦਿਖ ਰਿਹਾ ਹੈ। ਕੋਈ ਅਸਲ ਭੁਗਤਾਨ ਨਹੀਂ ਗਿਆ।"
        ),
        "done_plain": "ਮੈਂ ਸਕਰੀਨ ਅੱਪਡੇਟ ਕਰ ਦਿੱਤੀ ਹੈ। ਕੋਈ ਅਸਲ ਭੁਗਤਾਨ ਨਹੀਂ ਗਿਆ।",
        "clear": "ਠੀਕ ਹੈ। ਮੈਂ ਸਕਰੀਨ ਨਹੀਂ ਬਦਲਾਂਗਾ।",
    },
    "punjabi_roman": {
        "offer_status": (
            "Eh {label} varga lagda hai. Main screen te ehi status bhar sakda haan. "
            "Pay button nahi hai, dooja payment start nahi hovega. Haan likho."
        ),
        "offer_renew": (
            "Eh {label} varga lagda hai. Main is screen te UPI autopay renew kar sakda haan. "
            "Koi asli payment nahi jawegi. Main {amount} te {bank} vartanga, "
            "jad tak tusi hor amount te last 4 digits na likho. "
            "Haan likho, main confirm bhar deanga. Proceed likho, main screen te poora kar deanga."
        ),
        "offer_pay": (
            "Eh {label} varga lagda hai. Main is screen te Pay this instalment khol sakda haan. "
            "Koi asli payment nahi jawegi. Main {amount} te {bank} vartanga. Haan likho."
        ),
        "filled": (
            "Main screen te {amount} te {bank} bhar ditta hai te confirm khol ditta hai. "
            "Proceed likho. Koi asli payment nahi jawegi."
        ),
        "done_status": "Main screen te {label} la ditta hai. Pay button nahi hai, is mahine fer charge nahi hovega.",
        "done_renew": (
            "Main screen te renew poora kar ditta hai, {amount}, {bank}. "
            "Autopay on dikh reha hai. Koi asli debit nahi gayi."
        ),
        "done_pay": (
            "Main screen te Pay this instalment poora kar ditta hai, {amount}, {bank}. "
            "Eh received dikh reha hai. Koi asli payment nahi gaya."
        ),
        "done_plain": "Main screen update kar ditti hai. Koi asli payment nahi gaya.",
        "clear": "Theek hai. Main screen nahi badlanga.",
    },
}


def _language(text, offer):
    language = detect_language(text)
    if not offer or not offer.get("language"):
        return language
    short = len((text or "").split()) <= 8
    if short and (YES_RE.search(text or "") or NO_RE.search(text or "") or FINISH_RE.search(text or "")):
        return offer["language"]
    return language


def _say(language, key, **kwargs):
    table = COPY.get(language) or COPY["english"]
    line = table.get(key) or COPY["english"][key]
    return line.format(**kwargs)


def _offer_text(scene, amount, bank, language):
    fields = {"label": scene["label"], "amount": amount, "bank": bank}
    if scene["kind"] == "status":
        return _say(language, "offer_status", **fields)
    if scene["kind"] == "renew":
        return _say(language, "offer_renew", **fields)
    if scene["kind"] == "bank":
        return _say(language, "offer_bank", **fields)
    return _say(language, "offer_pay", **fields)


def decide(message, offer, current_label):
    """Return pass, offer, apply, or clear. The page applies the screen on the next run."""
    text = (message or "").strip()
    if OTHER_RE.search(text):
        return {"type": "pass"}

    language = _language(text, offer)
    amount = (offer or {}).get("amount") or DEFAULT_AMOUNT
    bank = (offer or {}).get("bank") or DEFAULT_BANK
    amount, bank = read_details(text, amount, bank)
    details_changed = amount != ((offer or {}).get("amount") or DEFAULT_AMOUNT) or bank != (
        (offer or {}).get("bank") or DEFAULT_BANK
    )
    fields = {"label": (offer or {}).get("label") or "", "amount": amount, "bank": bank}

    if offer and NO_RE.search(text) and not FINISH_RE.search(text):
        return {"type": "clear", "text": _say(language, "clear")}

    if offer and offer.get("phase") == "finishing" and (YES_RE.search(text) or FINISH_RE.search(text)):
        scene = _scene_by_label(offer["label"])
        step = "home" if scene and scene["kind"] == "status" else "done"
        fields["label"] = offer["label"]
        return {
            "type": "apply",
            "text": _done_text(scene, language, fields),
            "situation": offer["label"],
            "step": step,
            "amount": amount,
            "bank": bank,
            "offer": None,
        }

    if offer and (YES_RE.search(text) or FINISH_RE.search(text) or details_changed):
        scene = _scene_by_label(offer["label"])
        fields["label"] = scene["label"] if scene else ""
        if scene and scene["kind"] == "status":
            step = "home"
            phase_offer = None
            reply = _done_text(scene, language, fields)
        else:
            step = "done"
            phase_offer = None
            reply = _done_text(scene, language, fields)
        return {
            "type": "apply",
            "text": reply,
            "situation": scene["label"],
            "step": step,
            "amount": amount,
            "bank": bank,
            "offer": phase_offer,
        }

    scene = classify(text)
    if scene is None and HELP_RE.search(text):
        scene = _scene_by_label(current_label) or SCENES[-1]
    if scene is None:
        return {"type": "pass"}

    return {
        "type": "offer",
        "text": _offer_text(scene, amount, bank, language),
        "offer": {
            "label": scene["label"],
            "kind": scene["kind"],
            "phase": "ask",
            "amount": amount,
            "bank": bank,
            "language": language,
        },
    }


def _done_text(scene, language, fields):
    if scene is None:
        return _say(language, "done_plain", **fields)
    if scene["kind"] == "status":
        return _say(language, "done_status", **fields)
    if scene["kind"] == "renew":
        return _say(language, "done_renew", **fields)
    if scene["kind"] == "bank":
        return _say(language, "done_bank", **fields)
    return _say(language, "done_pay", **fields)
