"""Words the backend says to people outside the worker's messages (round 5).

The languages every backend text is written in, the locale → language rule, and
the texts core_api sends or shows itself: the sign-in code (SMS), the welcome
email, the quick messages between customer and rider (B2) and the names used
when someone has none. The worker's order and payout messages are in
``worker/app/services/messages.py`` and follow the same rules.

Every text has every language in ``LANGUAGES``, with the same {placeholders} as
English; ``python tools/i18n/check_locales.py`` (make ci-i18n) fails when a
language a live country lists in Markets is missing or empty. English is the
source; the other languages are machine translations awaiting native review
(packages/i18n/REVIEW.md, "Backend messages").

Voice: plain, specific, warm. Never blame anyone. No emoji. Quick messages never
ask for a call and carry no digits (nobody's phone number is shared).

Stdlib only: the CI check imports this file without the backend's packages.
"""

# Every language we write in (the same as packages/i18n/messages).
LANGUAGES: tuple[str, ...] = ("en", "hi", "te", "ta", "kn", "mr", "bn", "es")


def language_for(locale: str | None) -> str:
    """A Markets locale or a language → one of LANGUAGES: hi-IN → hi, es-US → es,
    anything we don't write in → en."""
    lang = (locale or "en").replace("_", "-").split("-")[0].lower()
    return lang if lang in LANGUAGES else "en"


def pick(texts: dict[str, str], language: str) -> str:
    """The text in ``language``, else English."""
    return texts.get(language) or texts["en"]


# ── quick messages (B2) ──────────────────────────────────────────────────────
# Each side reads them in their own language: a preset is stored by key and
# translated for the reader; free text is shown as written.
QUICK_PRESETS: dict[str, dict[str, dict[str, str]]] = {
    "rider": {
        "at_kitchen": {
            "en": "I'm at the kitchen, waiting for your order.",
            "hi": "मैं किचन पर हूं, आपके ऑर्डर का इंतज़ार है।",
            "te": "నేను కిచెన్ దగ్గర ఉన్నాను, మీ ఆర్డర్ కోసం ఎదురుచూస్తున్నాను.",
            "ta": "நான் சமையலறையில் இருக்கிறேன், உங்கள் ஆர்டருக்காகக் காத்திருக்கிறேன்.",
            "kn": "ನಾನು ಅಡುಗೆಮನೆಯ ಬಳಿ ಇದ್ದೇನೆ, ನಿಮ್ಮ ಆರ್ಡರ್‌ಗಾಗಿ ಕಾಯುತ್ತಿದ್ದೇನೆ.",
            "mr": "मी किचनजवळ आहे, तुमच्या ऑर्डरची वाट पाहत आहे.",
            "bn": "আমি কিচেনে আছি, আপনার অর্ডারের জন্য অপেক্ষা করছি।",
            "es": "Estoy en la cocina, esperando tu pedido.",
        },
        "on_my_way": {
            "en": "Picked up. On my way to you.",
            "hi": "ऑर्डर ले लिया है। आपके पास आ रहे हैं।",
            "te": "ఆర్డర్ తీసుకున్నాను. మీ దగ్గరికి వస్తున్నాను.",
            "ta": "ஆர்டரை எடுத்துவிட்டேன். உங்களிடம் வந்துகொண்டிருக்கிறேன்.",
            "kn": "ಆರ್ಡರ್ ತೆಗೆದುಕೊಂಡಿದ್ದೇನೆ. ನಿಮ್ಮ ಬಳಿ ಬರುತ್ತಿದ್ದೇನೆ.",
            "mr": "ऑर्डर घेतली आहे. तुमच्याकडे येत आहे.",
            "bn": "অর্ডার নিয়েছি। আপনার কাছে আসছি।",
            "es": "Ya lo recogí. Voy en camino.",
        },
        "outside": {
            "en": "I'm outside.",
            "hi": "मैं बाहर हूं।",
            "te": "నేను బయట ఉన్నాను.",
            "ta": "நான் வெளியே இருக்கிறேன்.",
            "kn": "ನಾನು ಹೊರಗೆ ಇದ್ದೇನೆ.",
            "mr": "मी बाहेर आहे.",
            "bn": "আমি বাইরে আছি।",
            "es": "Estoy afuera.",
        },
        "cant_find": {
            "en": "I can't find the address. Please check the pin on the map.",
            "hi": "पता नहीं मिल रहा। कृपया मैप पर पिन देख लें।",
            "te": "చిరునామా దొరకడం లేదు. దయచేసి మ్యాప్‌లో పిన్ చూడండి.",
            "ta": "முகவரி கிடைக்கவில்லை. வரைபடத்தில் உள்ள பின்னைச் சரிபார்க்கவும்.",
            "kn": "ವಿಳಾಸ ಸಿಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ನಕ್ಷೆಯಲ್ಲಿನ ಪಿನ್ ಪರಿಶೀಲಿಸಿ.",
            "mr": "पत्ता सापडत नाही. कृपया नकाशावरील पिन तपासा.",
            "bn": "ঠিকানা খুঁজে পাচ্ছি না। দয়া করে ম্যাপে পিনটি দেখুন।",
            "es": "No encuentro la dirección. Revisa el pin en el mapa, por favor.",
        },
        "running_late": {
            "en": "Running a few minutes late, sorry.",
            "hi": "माफ़ कीजिए, कुछ मिनट की देरी हो रही है।",
            "te": "క్షమించండి, కొన్ని నిమిషాలు ఆలస్యం అవుతోంది.",
            "ta": "மன்னிக்கவும், சில நிமிடங்கள் தாமதமாகும்.",
            "kn": "ಕ್ಷಮಿಸಿ, ಕೆಲವು ನಿಮಿಷ ತಡವಾಗುತ್ತಿದೆ.",
            "mr": "माफ करा, काही मिनिटे उशीर होत आहे.",
            "bn": "দুঃখিত, কয়েক মিনিট দেরি হচ্ছে।",
            "es": "Voy unos minutos tarde, perdón.",
        },
    },
    "customer": {
        "leave_at_door": {
            "en": "Please leave it at the door.",
            "hi": "कृपया दरवाज़े पर रख दें।",
            "te": "దయచేసి తలుపు దగ్గర పెట్టండి.",
            "ta": "தயவுசெய்து வாசலில் வைத்துவிடுங்கள்.",
            "kn": "ದಯವಿಟ್ಟು ಬಾಗಿಲ ಬಳಿ ಇಡಿ.",
            "mr": "कृपया दाराजवळ ठेवा.",
            "bn": "দয়া করে দরজার সামনে রেখে দিন।",
            "es": "Déjalo en la puerta, por favor.",
        },
        "coming_down": {
            "en": "I'm coming down.",
            "hi": "बस नीचे आ रहे हैं।",
            "te": "నేను కిందకి వస్తున్నాను.",
            "ta": "நான் கீழே வருகிறேன்.",
            "kn": "ನಾನು ಕೆಳಗೆ ಬರುತ್ತಿದ್ದೇನೆ.",
            "mr": "मी खाली येत आहे.",
            "bn": "আমি নিচে আসছি।",
            "es": "Ya bajo.",
        },
        "ring_bell": {
            "en": "Please ring the bell.",
            "hi": "कृपया घंटी बजा दें।",
            "te": "దయచేసి బెల్ కొట్టండి.",
            "ta": "தயவுசெய்து மணியை அடியுங்கள்.",
            "kn": "ದಯವಿಟ್ಟು ಬೆಲ್ ಒತ್ತಿ.",
            "mr": "कृपया बेल वाजवा.",
            "bn": "দয়া করে বেল বাজান।",
            "es": "Toca el timbre, por favor.",
        },
        "ask_guard": {
            "en": "Please ask the guard at the gate.",
            "hi": "कृपया गेट पर गार्ड से पूछ लें।",
            "te": "దయచేసి గేటు దగ్గర గార్డును అడగండి.",
            "ta": "தயவுசெய்து வாயிலில் உள்ள காவலரிடம் கேளுங்கள்.",
            "kn": "ದಯವಿಟ್ಟು ಗೇಟ್‌ನಲ್ಲಿರುವ ಗಾರ್ಡ್ ಅವರನ್ನು ಕೇಳಿ.",
            "mr": "कृपया गेटवरील गार्डला विचारा.",
            "bn": "দয়া করে গেটের গার্ডকে জিজ্ঞেস করুন।",
            "es": "Pregúntale al guardia de la entrada, por favor.",
        },
    },
}


def preset_text(side: str, key: str | None, language: str) -> str | None:
    """A quick message in ``language`` (None when ``side`` has no such preset)."""
    texts = QUICK_PRESETS.get(side, {}).get(key or "")
    return pick(texts, language) if texts else None


# When someone has no name on their account (a message title, the chat header).
NAMES: dict[str, dict[str, str]] = {
    "your_rider": {
        "en": "Your rider", "hi": "आपका राइडर", "te": "మీ రైడర్", "ta": "உங்கள் ரைடர்",
        "kn": "ನಿಮ್ಮ ರೈಡರ್", "mr": "तुमचा रायडर", "bn": "আপনার রাইডার", "es": "Tu repartidor",
    },
    "the_customer": {
        "en": "The customer", "hi": "ग्राहक", "te": "కస్టమర్", "ta": "வாடிக்கையாளர்",
        "kn": "ಗ್ರಾಹಕರು", "mr": "ग्राहक", "bn": "গ্রাহক", "es": "El cliente",
    },
}


def fallback_name(role: str, language: str) -> str:
    """"Your rider" for a rider, "The customer" for a customer, in ``language``."""
    return pick(NAMES["your_rider" if role == "rider" else "the_customer"], language)


# ── sign-in code (SMS, core_api) ─────────────────────────────────────────────
# Sent as is (no "BhojanGo: " prefix: the brand is in the sentence). India: the
# DLT template key is "otp_<language>" with the variables otp, minutes.
OTP_SMS: dict[str, str] = {
    "en": "Your BhojanGo verification code is: {otp}. Valid for {minutes} minutes.",
    "hi": "आपका BhojanGo सत्यापन कोड {otp} है। यह {minutes} मिनट तक मान्य है।",
    "te": "మీ BhojanGo ధృవీకరణ కోడ్: {otp}. ఇది {minutes} నిమిషాల పాటు చెల్లుతుంది.",
    "ta": "உங்கள் BhojanGo சரிபார்ப்புக் குறியீடு: {otp}. இது {minutes} நிமிடங்களுக்குச் செல்லுபடியாகும்.",
    "kn": "ನಿಮ್ಮ BhojanGo ಪರಿಶೀಲನಾ ಕೋಡ್: {otp}. ಇದು {minutes} ನಿಮಿಷಗಳವರೆಗೆ ಮಾನ್ಯವಾಗಿರುತ್ತದೆ.",
    "mr": "तुमचा BhojanGo पडताळणी कोड {otp} आहे. तो {minutes} मिनिटे वैध आहे.",
    "bn": "আপনার BhojanGo যাচাইকরণ কোড {otp}। এটি {minutes} মিনিট বৈধ থাকবে।",
    "es": "Tu código de verificación de BhojanGo es {otp}. Vale por {minutes} minutos.",
}


# ── welcome email (core_api, on sign-up with email and password) ──────────────
WELCOME: dict[str, dict[str, str]] = {
    "subject": {
        "en": "Welcome to BhojanGo",
        "hi": "BhojanGo में आपका स्वागत है",
        "te": "BhojanGoకి స్వాగతం",
        "ta": "BhojanGo-க்கு வரவேற்கிறோம்",
        "kn": "BhojanGoಗೆ ಸ್ವಾಗತ",
        "mr": "BhojanGo मध्ये तुमचे स्वागत आहे",
        "bn": "BhojanGo-তে স্বাগতম",
        "es": "Te damos la bienvenida a BhojanGo",
    },
    "hello": {
        "en": "Hi {name},", "hi": "नमस्ते {name},", "te": "నమస్తే {name},", "ta": "வணக்கம் {name},",
        "kn": "ನಮಸ್ಕಾರ {name},", "mr": "नमस्कार {name},", "bn": "নমস্কার {name},", "es": "Hola, {name}:",
    },
    "hello_anon": {
        "en": "Hi there,", "hi": "नमस्ते,", "te": "నమస్తే,", "ta": "வணக்கம்,",
        "kn": "ನಮಸ್ಕಾರ,", "mr": "नमस्कार,", "bn": "নমস্কার,", "es": "Hola:",
    },
    "body": {
        "en": "Welcome to BhojanGo. Your account is ready: pick a restaurant near you and we'll bring the food over.",
        "hi": "BhojanGo में आपका स्वागत है। आपका खाता तैयार है: अपने पास का कोई रेस्टोरेंट चुनिए, खाना हम पहुंचा देंगे।",
        "te": "BhojanGoకి స్వాగతం. మీ ఖాతా సిద్ధంగా ఉంది: మీ దగ్గరలోని రెస్టారెంట్‌ను ఎంచుకోండి, భోజనం మేము తెస్తాం.",
        "ta": "BhojanGo-க்கு வரவேற்கிறோம். உங்கள் கணக்கு தயார்: அருகிலுள்ள ஒரு உணவகத்தைத் தேர்ந்தெடுங்கள், உணவை நாங்கள் கொண்டு வருகிறோம்.",
        "kn": "BhojanGoಗೆ ಸ್ವಾಗತ. ನಿಮ್ಮ ಖಾತೆ ಸಿದ್ಧವಾಗಿದೆ: ನಿಮ್ಮ ಹತ್ತಿರದ ರೆಸ್ಟೋರೆಂಟ್ ಆಯ್ಕೆಮಾಡಿ, ಊಟವನ್ನು ನಾವು ತಂದುಕೊಡುತ್ತೇವೆ.",
        "mr": "BhojanGo मध्ये तुमचे स्वागत आहे. तुमचे खाते तयार आहे: जवळचे एखादे रेस्टॉरंट निवडा, जेवण आम्ही घेऊन येऊ.",
        "bn": "BhojanGo-তে স্বাগতম। আপনার অ্যাকাউন্ট তৈরি: কাছের একটি রেস্তোরাঁ বেছে নিন, খাবার আমরা পৌঁছে দেব।",
        "es": "Te damos la bienvenida a BhojanGo. Tu cuenta está lista: elige un restaurante cerca de ti y te llevamos la comida.",
    },
    "signoff": {
        "en": "The BhojanGo team", "hi": "BhojanGo टीम", "te": "BhojanGo టీమ్", "ta": "BhojanGo குழு",
        "kn": "BhojanGo ತಂಡ", "mr": "BhojanGo टीम", "bn": "BhojanGo টিম", "es": "El equipo de BhojanGo",
    },
}


def entries() -> dict[str, dict[str, str]]:
    """Every text here as "<name>" → {language: text}, for the CI check."""
    out: dict[str, dict[str, str]] = {}
    for side, presets in QUICK_PRESETS.items():
        for key, texts in presets.items():
            out[f"chat.{side}.{key}"] = texts
    for key, texts in NAMES.items():
        out[f"names.{key}"] = texts
    out["otp_sms"] = OTP_SMS
    for key, texts in WELCOME.items():
        out[f"welcome.{key}"] = texts
    return out
