"""Words the backend says to people outside the worker's messages (round 5).

The languages every backend text is written in, the locale → language rule, and
the texts core_api sends or shows itself: the sign-in code (SMS), the welcome
email, the quick messages between customer and delivery partner (B2) and the names used
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
            "en": "I'm at the restaurant, waiting for your order.",
            "hi": "मैं रेस्टोरेंट पर हूं, आपके ऑर्डर का इंतज़ार है।",
            "te": "నేను రెస్టారెంట్ దగ్గర ఉన్నాను, మీ ఆర్డర్ కోసం ఎదురుచూస్తున్నాను.",
            "ta": "நான் உணவகத்தில் இருக்கிறேன், உங்கள் ஆர்டருக்காகக் காத்திருக்கிறேன்.",
            "kn": "ನಾನು ರೆಸ್ಟೋರೆಂಟ್ ಬಳಿ ಇದ್ದೇನೆ, ನಿಮ್ಮ ಆರ್ಡರ್‌ಗಾಗಿ ಕಾಯುತ್ತಿದ್ದೇನೆ.",
            "mr": "मी रेस्टॉरंटजवळ आहे, तुमच्या ऑर्डरची वाट पाहत आहे.",
            "bn": "আমি রেস্তোরাঁয় আছি, আপনার অর্ডারের জন্য অপেক্ষা করছি।",
            "es": "Estoy en el restaurante, esperando tu pedido.",
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
        "en": "Your delivery partner", "hi": "आपका डिलीवरी पार्टनर", "te": "మీ డెలివరీ పార్ట్‌నర్",
        "ta": "உங்கள் டெலிவரி பார்ட்னர்", "kn": "ನಿಮ್ಮ ಡೆಲಿವರಿ ಪಾರ್ಟ್ನರ್", "mr": "तुमचा डिलिव्हरी पार्टनर",
        "bn": "আপনার ডেলিভারি পার্টনার", "es": "Tu repartidor",
    },
    "the_customer": {
        "en": "The customer", "hi": "ग्राहक", "te": "కస్టమర్", "ta": "வாடிக்கையாளர்",
        "kn": "ಗ್ರಾಹಕರು", "mr": "ग्राहक", "bn": "গ্রাহক", "es": "El cliente",
    },
}


def fallback_name(role: str, language: str) -> str:
    """"Your delivery partner" for a delivery partner (role "rider"), "The customer" for a customer, in ``language``."""
    return pick(NAMES["your_rider" if role == "rider" else "the_customer"], language)


# ── fair-bill lines named by code (core_api) ─────────────────────────────────
# A bill line stored in an order's pricing snapshot keeps the label it was priced
# with ("Tip for your rider" before Round 8). Lines named here are relabelled by
# code whenever a bill goes out (pricing.service.lookup.customer_lines), so every
# client shows today's words, in the reader's language, for every order.
BILL_LINES: dict[str, dict[str, str]] = {
    "tip": {
        "en": "Tip for your delivery partner", "hi": "आपके डिलीवरी पार्टनर के लिए टिप",
        "te": "మీ డెలివరీ పార్ట్‌నర్‌కు టిప్", "ta": "உங்கள் டெலிவரி பார்ட்னருக்கு டிப்",
        "kn": "ನಿಮ್ಮ ಡೆಲಿವರಿ ಪಾರ್ಟ್ನರ್‌ಗೆ ಟಿಪ್", "mr": "तुमच्या डिलिव्हरी पार्टनरसाठी टिप",
        "bn": "আপনার ডেলিভারি পার্টনারের জন্য টিপ", "es": "Propina para tu repartidor",
    },
}


# R38: bill labels renamed since orders were priced (stored lines keep the old words; customers read the new).
RENAMED_LABELS = {"GST on platform fees": "GST on fees"}


def bill_line_label(code: str | None, label: str, language: str = "en") -> str:
    """Today's label for a bill line with this code, in ``language``; else ``label`` as stored (renamed ones: today's)."""
    texts = BILL_LINES.get(code or "")
    return pick(texts, language) if texts else RENAMED_LABELS.get(label, label)


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


# ── sign-in emails (core_api identity, Round 8 D5) ───────────────────────────
# {code}: 6 digits; {minutes}: how long it works; {link}: a website address.
AUTH_EMAILS: dict[str, dict[str, str]] = {
    "code.subject": {
        "en": "{code} is your BhojanGo code",
        "hi": "{code} आपका BhojanGo कोड है",
        "te": "{code} మీ BhojanGo కోడ్",
        "ta": "{code} உங்கள் BhojanGo குறியீடு",
        "kn": "{code} ನಿಮ್ಮ BhojanGo ಕೋಡ್",
        "mr": "{code} हा तुमचा BhojanGo कोड आहे",
        "bn": "{code} আপনার BhojanGo কোড",
        "es": "{code} es tu código de BhojanGo",
    },
    "code.body": {
        "en": "Enter this code in BhojanGo: {code}. It works for {minutes} minutes. If you didn't ask for it, you can ignore this email.",
        "hi": "BhojanGo में यह कोड डालें: {code}। यह {minutes} मिनट तक काम करेगा। अगर आपने यह नहीं मांगा था, तो इस ईमेल को अनदेखा कर दें।",
        "te": "BhojanGoలో ఈ కోడ్ నమోదు చేయండి: {code}. ఇది {minutes} నిమిషాల పాటు పని చేస్తుంది. మీరు దీన్ని అడగకపోతే, ఈ ఈమెయిల్‌ను పట్టించుకోవద్దు.",
        "ta": "BhojanGo-வில் இந்தக் குறியீட்டை உள்ளிடுங்கள்: {code}. இது {minutes} நிமிடங்கள் செல்லும். நீங்கள் இதைக் கேட்கவில்லை என்றால், இந்த மின்னஞ்சலைப் புறக்கணிக்கலாம்.",
        "kn": "BhojanGoನಲ್ಲಿ ಈ ಕೋಡ್ ನಮೂದಿಸಿ: {code}. ಇದು {minutes} ನಿಮಿಷಗಳವರೆಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ. ನೀವು ಇದನ್ನು ಕೇಳದಿದ್ದರೆ, ಈ ಇಮೇಲ್ ಅನ್ನು ನಿರ್ಲಕ್ಷಿಸಿ.",
        "mr": "BhojanGo मध्ये हा कोड टाका: {code}. तो {minutes} मिनिटे चालेल. तुम्ही तो मागितला नसेल, तर या ईमेलकडे दुर्लक्ष करा.",
        "bn": "BhojanGo-তে এই কোডটি দিন: {code}। এটি {minutes} মিনিট কাজ করবে। আপনি এটি না চাইলে এই ইমেলটি উপেক্ষা করুন।",
        "es": "Escribe este código en BhojanGo: {code}. Sirve durante {minutes} minutos. Si no lo pediste, puedes ignorar este correo.",
    },
    "exists.subject": {
        "en": "You already have a BhojanGo account",
        "hi": "आपका BhojanGo खाता पहले से है",
        "te": "మీకు ఇప్పటికే BhojanGo ఖాతా ఉంది",
        "ta": "உங்களுக்கு ஏற்கனவே BhojanGo கணக்கு உள்ளது",
        "kn": "ನಿಮಗೆ ಈಗಾಗಲೇ BhojanGo ಖಾತೆ ಇದೆ",
        "mr": "तुमचे BhojanGo खाते आधीच आहे",
        "bn": "আপনার আগে থেকেই একটি BhojanGo অ্যাকাউন্ট আছে",
        "es": "Ya tienes una cuenta de BhojanGo",
    },
    "exists.body": {
        "en": "Someone, probably you, tried to create a BhojanGo account with this email. You already have one: sign in with your password or ask for an email code. Forgot your password? Choose a new one here: {link}. If it wasn't you, you can ignore this email.",
        "hi": "किसी ने, शायद आपने, इस ईमेल से BhojanGo खाता बनाने की कोशिश की। आपका खाता पहले से है: अपने पासवर्ड से साइन इन करें या ईमेल कोड मांगें। पासवर्ड भूल गए? यहां नया चुनें: {link}। अगर यह आप नहीं थे, तो इस ईमेल को अनदेखा कर दें।",
        "te": "ఎవరో, బహుశా మీరే, ఈ ఈమెయిల్‌తో BhojanGo ఖాతా సృష్టించడానికి ప్రయత్నించారు. మీకు ఇప్పటికే ఖాతా ఉంది: మీ పాస్‌వర్డ్‌తో సైన్ ఇన్ చేయండి లేదా ఈమెయిల్ కోడ్ అడగండి. పాస్‌వర్డ్ మర్చిపోయారా? కొత్తది ఇక్కడ ఎంచుకోండి: {link}. అది మీరు కాకపోతే, ఈ ఈమెయిల్‌ను పట్టించుకోవద్దు.",
        "ta": "யாரோ, ஒருவேளை நீங்களே, இந்த மின்னஞ்சலில் BhojanGo கணக்கை உருவாக்க முயன்றார்கள். உங்களுக்கு ஏற்கனவே கணக்கு உள்ளது: கடவுச்சொல்லுடன் உள்நுழையுங்கள் அல்லது மின்னஞ்சல் குறியீட்டைக் கேளுங்கள். கடவுச்சொல் மறந்துவிட்டதா? புதியதை இங்கே தேர்ந்தெடுங்கள்: {link}. அது நீங்கள் இல்லையென்றால், இந்த மின்னஞ்சலைப் புறக்கணிக்கலாம்.",
        "kn": "ಯಾರೋ, ಬಹುಶಃ ನೀವೇ, ಈ ಇಮೇಲ್‌ನಿಂದ BhojanGo ಖಾತೆ ರಚಿಸಲು ಪ್ರಯತ್ನಿಸಿದರು. ನಿಮಗೆ ಈಗಾಗಲೇ ಖಾತೆ ಇದೆ: ನಿಮ್ಮ ಪಾಸ್‌ವರ್ಡ್‌ನಿಂದ ಸೈನ್ ಇನ್ ಮಾಡಿ ಅಥವಾ ಇಮೇಲ್ ಕೋಡ್ ಕೇಳಿ. ಪಾಸ್‌ವರ್ಡ್ ಮರೆತಿರಾ? ಹೊಸದನ್ನು ಇಲ್ಲಿ ಆಯ್ಕೆಮಾಡಿ: {link}. ಅದು ನೀವಲ್ಲದಿದ್ದರೆ, ಈ ಇಮೇಲ್ ಅನ್ನು ನಿರ್ಲಕ್ಷಿಸಿ.",
        "mr": "कोणीतरी, बहुधा तुम्हीच, या ईमेलने BhojanGo खाते तयार करण्याचा प्रयत्न केला. तुमचे खाते आधीच आहे: तुमच्या पासवर्डने साइन इन करा किंवा ईमेल कोड मागा. पासवर्ड विसरलात? नवीन इथे निवडा: {link}. ते तुम्ही नसाल, तर या ईमेलकडे दुर्लक्ष करा.",
        "bn": "কেউ, সম্ভবত আপনি, এই ইমেল দিয়ে একটি BhojanGo অ্যাকাউন্ট তৈরির চেষ্টা করেছেন। আপনার আগে থেকেই অ্যাকাউন্ট আছে: পাসওয়ার্ড দিয়ে সাইন ইন করুন বা ইমেল কোড চান। পাসওয়ার্ড ভুলে গেছেন? এখানে নতুন একটি বেছে নিন: {link}। এটি আপনি না হলে এই ইমেলটি উপেক্ষা করুন।",
        "es": "Alguien, probablemente tú, intentó crear una cuenta de BhojanGo con este correo. Ya tienes una: inicia sesión con tu contraseña o pide un código por correo. ¿Olvidaste tu contraseña? Elige una nueva aquí: {link}. Si no fuiste tú, puedes ignorar este correo.",
    },
    "reset.subject": {
        "en": "Choose a new BhojanGo password",
        "hi": "BhojanGo का नया पासवर्ड चुनें",
        "te": "కొత్త BhojanGo పాస్‌వర్డ్ ఎంచుకోండి",
        "ta": "புதிய BhojanGo கடவுச்சொல்லைத் தேர்ந்தெடுங்கள்",
        "kn": "ಹೊಸ BhojanGo ಪಾಸ್‌ವರ್ಡ್ ಆಯ್ಕೆಮಾಡಿ",
        "mr": "BhojanGo चा नवीन पासवर्ड निवडा",
        "bn": "BhojanGo-এর নতুন পাসওয়ার্ড বেছে নিন",
        "es": "Elige una nueva contraseña de BhojanGo",
    },
    "reset.body": {
        "en": "To choose a new password, open this link. It works once, for {minutes} minutes: {link}. If you didn't ask for this, ignore this email and your password stays the same.",
        "hi": "नया पासवर्ड चुनने के लिए यह लिंक खोलें। यह एक बार, {minutes} मिनट तक काम करेगा: {link}। अगर आपने यह नहीं मांगा था, तो इस ईमेल को अनदेखा करें; आपका पासवर्ड वही रहेगा।",
        "te": "కొత్త పాస్‌వర్డ్ ఎంచుకోవడానికి ఈ లింక్ తెరవండి. ఇది ఒక్కసారి, {minutes} నిమిషాల పాటు పని చేస్తుంది: {link}. మీరు దీన్ని అడగకపోతే, ఈ ఈమెయిల్‌ను పట్టించుకోవద్దు; మీ పాస్‌వర్డ్ మారదు.",
        "ta": "புதிய கடவுச்சொல்லைத் தேர்ந்தெடுக்க இந்த இணைப்பைத் திறங்கள். இது ஒரே ஒரு முறை, {minutes} நிமிடங்கள் செல்லும்: {link}. நீங்கள் இதைக் கேட்கவில்லை என்றால், இந்த மின்னஞ்சலைப் புறக்கணியுங்கள்; உங்கள் கடவுச்சொல் மாறாது.",
        "kn": "ಹೊಸ ಪಾಸ್‌ವರ್ಡ್ ಆಯ್ಕೆಮಾಡಲು ಈ ಲಿಂಕ್ ತೆರೆಯಿರಿ. ಇದು ಒಮ್ಮೆ ಮಾತ್ರ, {minutes} ನಿಮಿಷಗಳವರೆಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ: {link}. ನೀವು ಇದನ್ನು ಕೇಳದಿದ್ದರೆ, ಈ ಇಮೇಲ್ ಅನ್ನು ನಿರ್ಲಕ್ಷಿಸಿ; ನಿಮ್ಮ ಪಾಸ್‌ವರ್ಡ್ ಬದಲಾಗುವುದಿಲ್ಲ.",
        "mr": "नवीन पासवर्ड निवडण्यासाठी ही लिंक उघडा. ती एकदाच, {minutes} मिनिटे चालेल: {link}. तुम्ही हे मागितले नसेल, तर या ईमेलकडे दुर्लक्ष करा; तुमचा पासवर्ड तसाच राहील.",
        "bn": "নতুন পাসওয়ার্ড বেছে নিতে এই লিংকটি খুলুন। এটি একবারই, {minutes} মিনিট কাজ করবে: {link}। আপনি এটি না চাইলে এই ইমেলটি উপেক্ষা করুন; আপনার পাসওয়ার্ড একই থাকবে।",
        "es": "Para elegir una nueva contraseña, abre este enlace. Sirve una sola vez, durante {minutes} minutos: {link}. Si no lo pediste, ignora este correo y tu contraseña no cambiará.",
    },
    "changed.subject": {
        "en": "Your BhojanGo password was changed",
        "hi": "आपका BhojanGo पासवर्ड बदल दिया गया",
        "te": "మీ BhojanGo పాస్‌వర్డ్ మార్చబడింది",
        "ta": "உங்கள் BhojanGo கடவுச்சொல் மாற்றப்பட்டது",
        "kn": "ನಿಮ್ಮ BhojanGo ಪಾಸ್‌ವರ್ಡ್ ಬದಲಾಗಿದೆ",
        "mr": "तुमचा BhojanGo पासवर्ड बदलला गेला",
        "bn": "আপনার BhojanGo পাসওয়ার্ড বদলানো হয়েছে",
        "es": "Se cambió tu contraseña de BhojanGo",
    },
    "changed.body": {
        "en": "Your BhojanGo password was just changed, and your other devices were signed out. If this wasn't you, choose a new password now: {link}",
        "hi": "आपका BhojanGo पासवर्ड अभी बदला गया है, और आपके दूसरे डिवाइस से साइन आउट कर दिया गया है। अगर यह आप नहीं थे, तो अभी नया पासवर्ड चुनें: {link}",
        "te": "మీ BhojanGo పాస్‌వర్డ్ ఇప్పుడే మార్చబడింది, మీ ఇతర పరికరాల నుండి సైన్ అవుట్ చేయబడింది. అది మీరు కాకపోతే, ఇప్పుడే కొత్త పాస్‌వర్డ్ ఎంచుకోండి: {link}",
        "ta": "உங்கள் BhojanGo கடவுச்சொல் இப்போது மாற்றப்பட்டது, உங்கள் மற்ற சாதனங்களிலிருந்து வெளியேற்றப்பட்டது. அது நீங்கள் இல்லையென்றால், இப்போதே புதிய கடவுச்சொல்லைத் தேர்ந்தெடுங்கள்: {link}",
        "kn": "ನಿಮ್ಮ BhojanGo ಪಾಸ್‌ವರ್ಡ್ ಈಗಷ್ಟೇ ಬದಲಾಗಿದೆ, ಮತ್ತು ನಿಮ್ಮ ಇತರ ಸಾಧನಗಳಿಂದ ಸೈನ್ ಔಟ್ ಮಾಡಲಾಗಿದೆ. ಅದು ನೀವಲ್ಲದಿದ್ದರೆ, ಈಗಲೇ ಹೊಸ ಪಾಸ್‌ವರ್ಡ್ ಆಯ್ಕೆಮಾಡಿ: {link}",
        "mr": "तुमचा BhojanGo पासवर्ड आत्ताच बदलला गेला, आणि तुमच्या इतर डिव्हाइसवरून साइन आउट केले गेले. ते तुम्ही नसाल, तर आत्ताच नवीन पासवर्ड निवडा: {link}",
        "bn": "আপনার BhojanGo পাসওয়ার্ড এইমাত্র বদলানো হয়েছে, আর আপনার অন্য ডিভাইসগুলো থেকে সাইন আউট করা হয়েছে। এটি আপনি না হলে এখনই নতুন পাসওয়ার্ড বেছে নিন: {link}",
        "es": "Se acaba de cambiar tu contraseña de BhojanGo y se cerró la sesión en tus otros dispositivos. Si no fuiste tú, elige una nueva contraseña ahora: {link}",
    },
    "email_replaced.subject": {
        "en": "The email on your BhojanGo account was changed",
        "hi": "आपके BhojanGo खाते का ईमेल बदल दिया गया",
        "te": "మీ BhojanGo ఖాతా ఈమెయిల్ మార్చబడింది",
        "ta": "உங்கள் BhojanGo கணக்கின் மின்னஞ்சல் மாற்றப்பட்டது",
        "kn": "ನಿಮ್ಮ BhojanGo ಖಾತೆಯ ಇಮೇಲ್ ಬದಲಾಗಿದೆ",
        "mr": "तुमच्या BhojanGo खात्याचा ईमेल बदलला गेला",
        "bn": "আপনার BhojanGo অ্যাকাউন্টের ইমেল বদলানো হয়েছে",
        "es": "Se cambió el correo de tu cuenta de BhojanGo",
    },
    "email_replaced.body": {
        "en": "Your BhojanGo account now uses a different email address, so this one won't get our messages any more. If this wasn't you, contact BhojanGo support straight away.",
        "hi": "आपका BhojanGo खाता अब दूसरा ईमेल पता इस्तेमाल करता है, इसलिए इस पते पर अब हमारे संदेश नहीं आएंगे। अगर यह आप नहीं थे, तो तुरंत BhojanGo सहायता से संपर्क करें।",
        "te": "మీ BhojanGo ఖాతా ఇప్పుడు వేరే ఈమెయిల్ చిరునామాను ఉపయోగిస్తోంది, కాబట్టి ఈ చిరునామాకు ఇకపై మా సందేశాలు రావు. అది మీరు కాకపోతే, వెంటనే BhojanGo సపోర్ట్‌ను సంప్రదించండి.",
        "ta": "உங்கள் BhojanGo கணக்கு இப்போது வேறு மின்னஞ்சல் முகவரியைப் பயன்படுத்துகிறது, எனவே இந்த முகவரிக்கு இனி எங்கள் செய்திகள் வராது. அது நீங்கள் இல்லையென்றால், உடனே BhojanGo உதவியைத் தொடர்புகொள்ளுங்கள்.",
        "kn": "ನಿಮ್ಮ BhojanGo ಖಾತೆ ಈಗ ಬೇರೆ ಇಮೇಲ್ ವಿಳಾಸವನ್ನು ಬಳಸುತ್ತದೆ, ಹಾಗಾಗಿ ಈ ವಿಳಾಸಕ್ಕೆ ಇನ್ನು ನಮ್ಮ ಸಂದೇಶಗಳು ಬರುವುದಿಲ್ಲ. ಅದು ನೀವಲ್ಲದಿದ್ದರೆ, ತಕ್ಷಣ BhojanGo ಸಹಾಯವನ್ನು ಸಂಪರ್ಕಿಸಿ.",
        "mr": "तुमचे BhojanGo खाते आता दुसरा ईमेल पत्ता वापरते, त्यामुळे या पत्त्यावर आता आमचे संदेश येणार नाहीत. ते तुम्ही नसाल, तर लगेच BhojanGo सहाय्याशी संपर्क साधा.",
        "bn": "আপনার BhojanGo অ্যাকাউন্ট এখন অন্য একটি ইমেল ঠিকানা ব্যবহার করে, তাই এই ঠিকানায় আর আমাদের বার্তা আসবে না। এটি আপনি না হলে এখনই BhojanGo সহায়তায় যোগাযোগ করুন।",
        "es": "Tu cuenta de BhojanGo ahora usa otra dirección de correo, así que esta ya no recibirá nuestros mensajes. Si no fuiste tú, contacta con el soporte de BhojanGo de inmediato.",
    },
}


# The email a new restaurant partner gets when they start an application on the
# website (POST /kitchens/apply). {kitchen} is the restaurant's name (R30: the copy says restaurant).
KITCHEN_APPLIED: dict[str, dict[str, str]] = {
    "subject": {
        "en": "Your BhojanGo restaurant application has started",
        "hi": "BhojanGo पर आपके रेस्टोरेंट का आवेदन शुरू हो गया है",
        "te": "BhojanGoలో మీ రెస్టారెంట్ దరఖాస్తు మొదలైంది",
        "ta": "BhojanGo-வில் உங்கள் உணவக விண்ணப்பம் தொடங்கியது",
        "kn": "BhojanGoನಲ್ಲಿ ನಿಮ್ಮ ರೆಸ್ಟೋರೆಂಟ್ ಅರ್ಜಿ ಆರಂಭವಾಗಿದೆ",
        "mr": "BhojanGo वर तुमच्या रेस्टॉरंटचा अर्ज सुरू झाला आहे",
        "bn": "BhojanGo-তে আপনার রেস্তোরাঁর আবেদন শুরু হয়েছে",
        "es": "Tu solicitud de restaurante en BhojanGo ha comenzado",
    },
    "body": {
        "en": "Thanks for applying with {kitchen}. Your restaurant partner account is ready: sign in with this email and your password.",
        "hi": "{kitchen} के साथ आवेदन करने के लिए धन्यवाद। आपका रेस्टोरेंट पार्टनर खाता तैयार है: इसी ईमेल और अपने पासवर्ड से साइन इन करें।",
        "te": "{kitchen}తో దరఖాస్తు చేసినందుకు ధన్యవాదాలు. మీ రెస్టారెంట్ పార్ట్‌నర్ ఖాతా సిద్ధంగా ఉంది: ఈ ఈమెయిల్, మీ పాస్‌వర్డ్‌తో సైన్ ఇన్ చేయండి.",
        "ta": "{kitchen} உடன் விண்ணப்பித்ததற்கு நன்றி. உங்கள் உணவக கூட்டாளர் கணக்கு தயார்: இந்த மின்னஞ்சல் மற்றும் உங்கள் கடவுச்சொல்லுடன் உள்நுழையுங்கள்.",
        "kn": "{kitchen} ಜೊತೆ ಅರ್ಜಿ ಸಲ್ಲಿಸಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು. ನಿಮ್ಮ ರೆಸ್ಟೋರೆಂಟ್ ಪಾಲುದಾರ ಖಾತೆ ಸಿದ್ಧವಾಗಿದೆ: ಈ ಇಮೇಲ್ ಮತ್ತು ನಿಮ್ಮ ಪಾಸ್‌ವರ್ಡ್‌ನಿಂದ ಸೈನ್ ಇನ್ ಮಾಡಿ.",
        "mr": "{kitchen} सह अर्ज केल्याबद्दल धन्यवाद. तुमचे रेस्टॉरंट पार्टनर खाते तयार आहे: याच ईमेल आणि तुमच्या पासवर्डने साइन इन करा.",
        "bn": "{kitchen} নিয়ে আবেদন করার জন্য ধন্যবাদ। আপনার রেস্তোরাঁ পার্টনার অ্যাকাউন্ট তৈরি: এই ইমেল আর আপনার পাসওয়ার্ড দিয়ে সাইন ইন করুন।",
        "es": "Gracias por presentar la solicitud de {kitchen}. Tu cuenta de socio restaurante está lista: inicia sesión con este correo y tu contraseña.",
    },
    "next": {
        "en": "Next: your business details, licences, tax and bank account on the website's \"Add your restaurant\" page, then your menu and photos in the BhojanGo Restaurant app. We check everything before your restaurant goes live.",
        "hi": "आगे: वेबसाइट के \"अपना रेस्टोरेंट जोड़ें\" पेज पर अपने व्यवसाय का ब्योरा, लाइसेंस, टैक्स और बैंक खाता, फिर BhojanGo Restaurant ऐप में अपना मेन्यू और फ़ोटो। आपका रेस्टोरेंट लाइव होने से पहले हम सब कुछ जांचते हैं।",
        "te": "తర్వాత: వెబ్‌సైట్‌లోని \"మీ రెస్టారెంట్ చేర్చండి\" పేజీలో మీ వ్యాపార వివరాలు, లైసెన్సులు, పన్ను, బ్యాంక్ ఖాతా; ఆ తర్వాత BhojanGo Restaurant యాప్‌లో మీ మెనూ, ఫోటోలు. మీ రెస్టారెంట్ లైవ్ అయ్యే ముందు మేము అన్నీ తనిఖీ చేస్తాం.",
        "ta": "அடுத்து: இணையதளத்தின் \"உங்கள் உணவகத்தைச் சேர்க்கவும்\" பக்கத்தில் உங்கள் வணிக விவரங்கள், உரிமங்கள், வரி மற்றும் வங்கிக் கணக்கு; பிறகு BhojanGo Restaurant செயலியில் உங்கள் மெனு மற்றும் புகைப்படங்கள். உங்கள் உணவகம் நேரலைக்கு வருமுன் அனைத்தையும் சரிபார்க்கிறோம்.",
        "kn": "ಮುಂದೆ: ವೆಬ್‌ಸೈಟ್‌ನ \"ನಿಮ್ಮ ರೆಸ್ಟೋರೆಂಟ್ ಸೇರಿಸಿ\" ಪುಟದಲ್ಲಿ ನಿಮ್ಮ ವ್ಯಾಪಾರ ವಿವರಗಳು, ಪರವಾನಗಿಗಳು, ತೆರಿಗೆ ಮತ್ತು ಬ್ಯಾಂಕ್ ಖಾತೆ; ನಂತರ BhojanGo Restaurant ಆ್ಯಪ್‌ನಲ್ಲಿ ನಿಮ್ಮ ಮೆನು ಮತ್ತು ಫೋಟೋಗಳು. ನಿಮ್ಮ ರೆಸ್ಟೋರೆಂಟ್ ಲೈವ್ ಆಗುವ ಮೊದಲು ನಾವು ಎಲ್ಲವನ್ನೂ ಪರಿಶೀಲಿಸುತ್ತೇವೆ.",
        "mr": "पुढे: वेबसाइटच्या \"तुमचे रेस्टॉरंट जोडा\" पानावर तुमच्या व्यवसायाचा तपशील, परवाने, कर आणि बँक खाते; मग BhojanGo Restaurant ॲपमध्ये तुमचा मेन्यू आणि फोटो. तुमचे रेस्टॉरंट लाइव्ह होण्यापूर्वी आम्ही सर्व काही तपासतो.",
        "bn": "এরপর: ওয়েবসাইটের \"আপনার রেস্তোরাঁ যোগ করুন\" পাতায় আপনার ব্যবসার বিবরণ, লাইসেন্স, ট্যাক্স ও ব্যাঙ্ক অ্যাকাউন্ট; তারপর BhojanGo Restaurant অ্যাপে আপনার মেনু ও ছবি। আপনার রেস্তোরাঁ লাইভ হওয়ার আগে আমরা সব কিছু যাচাই করি।",
        "es": "Después: los datos de tu negocio, licencias, impuestos y cuenta bancaria en la página \"Registra tu restaurante\" del sitio web, y luego tu menú y fotos en la app BhojanGo Restaurant. Revisamos todo antes de que tu restaurante esté activo.",
    },
}


# Why POST /riders/apply refused a delivery partner's sign-up (R9): the country's
# minimum age and allowed vehicles (Markets). {age}: the minimum age in years.
DELIVERY_SIGN_UP: dict[str, dict[str, str]] = {
    "under_age": {
        "en": "You need to be {age} or older to deliver with BhojanGo in this country.",
        "hi": "इस देश में BhojanGo के साथ डिलीवरी करने के लिए आपकी उम्र कम से कम {age} साल होनी चाहिए।",
        "te": "ఈ దేశంలో BhojanGoతో డెలివరీ చేయడానికి మీ వయస్సు కనీసం {age} సంవత్సరాలు ఉండాలి.",
        "ta": "இந்த நாட்டில் BhojanGo உடன் டெலிவரி செய்ய உங்களுக்குக் குறைந்தது {age} வயது ஆகியிருக்க வேண்டும்.",
        "kn": "ಈ ದೇಶದಲ್ಲಿ BhojanGo ಜೊತೆ ಡೆಲಿವರಿ ಮಾಡಲು ನಿಮಗೆ ಕನಿಷ್ಠ {age} ವರ್ಷ ವಯಸ್ಸಾಗಿರಬೇಕು.",
        "mr": "या देशात BhojanGo सोबत डिलिव्हरी करण्यासाठी तुमचे वय किमान {age} वर्षे असायला हवे.",
        "bn": "এই দেশে BhojanGo-র সঙ্গে ডেলিভারি করতে আপনার বয়স অন্তত {age} বছর হতে হবে।",
        "es": "Necesitas tener {age} años o más para repartir con BhojanGo en este país.",
    },
    "vehicle": {
        "en": "That vehicle can't be used for deliveries in this country. Pick one from the list.",
        "hi": "इस देश में इस वाहन से डिलीवरी नहीं की जा सकती। सूची में से कोई वाहन चुनें।",
        "te": "ఈ దేశంలో ఆ వాహనంతో డెలివరీ చేయలేరు. జాబితాలో ఉన్న వాహనాన్ని ఎంచుకోండి.",
        "ta": "இந்த நாட்டில் அந்த வாகனத்தைக் கொண்டு டெலிவரி செய்ய முடியாது. பட்டியலில் உள்ள ஒன்றைத் தேர்ந்தெடுங்கள்.",
        "kn": "ಈ ದೇಶದಲ್ಲಿ ಆ ವಾಹನದಿಂದ ಡೆಲಿವರಿ ಮಾಡಲು ಆಗುವುದಿಲ್ಲ. ಪಟ್ಟಿಯಲ್ಲಿರುವ ಒಂದನ್ನು ಆಯ್ಕೆಮಾಡಿ.",
        "mr": "या देशात त्या वाहनाने डिलिव्हरी करता येत नाही. यादीतील एखादे वाहन निवडा.",
        "bn": "এই দেশে ওই যানবাহন দিয়ে ডেলিভারি করা যায় না। তালিকা থেকে একটি বেছে নিন।",
        "es": "Ese vehículo no se puede usar para repartir en este país. Elige uno de la lista.",
    },
    "dob": {
        "en": "Check your date of birth.",
        "hi": "अपनी जन्मतिथि जांच लें।",
        "te": "మీ పుట్టిన తేదీని ఒకసారి చూసుకోండి.",
        "ta": "உங்கள் பிறந்த தேதியைச் சரிபார்க்கவும்.",
        "kn": "ನಿಮ್ಮ ಜನ್ಮ ದಿನಾಂಕವನ್ನು ಪರಿಶೀಲಿಸಿ.",
        "mr": "तुमची जन्मतारीख तपासा.",
        "bn": "আপনার জন্মতারিখটি দেখে নিন।",
        "es": "Revisa tu fecha de nacimiento.",
    },
}


# R17 incident messages (docs/launch/incident-plan.md "Customer messages"): sent by admin's bulk
# message tool by push and email, each customer in their own language. (title, body) per language,
# like the worker's CATALOGUE, which takes these in as "incident_<key>". Placeholders: {restaurant},
# {code} and {amount} come from each order (customers of a bulk refund); {time} from the admin; {area} is the
# recipients' city.
INCIDENT_MESSAGES: dict[str, dict[str, tuple[str, str]]] = {
    "order_cancelled": {
        "en": ("Your order was cancelled", "We're sorry: {restaurant} can't finish your order {code}. We've cancelled it and refunded {amount} to how you paid; it usually shows in 3–5 working days."),
        "hi": ("आपका ऑर्डर रद्द हुआ", "माफ़ कीजिए: {restaurant} आपका ऑर्डर {code} पूरा नहीं कर सकता। हमने इसे रद्द करके {amount} आपके भुगतान के तरीके में वापस कर दिए हैं; आमतौर पर 3–5 कार्यदिवस में दिखता है।"),
        "te": ("మీ ఆర్డర్ రద్దయింది", "క్షమించండి: {restaurant} మీ ఆర్డర్ {code}ని పూర్తి చేయలేదు. మేము దాన్ని రద్దు చేసి {amount} మీరు చెల్లించిన విధానానికి తిరిగి ఇచ్చాం; సాధారణంగా 3–5 పని దినాల్లో కనిపిస్తుంది."),
        "ta": ("உங்கள் ஆர்டர் ரத்து செய்யப்பட்டது", "மன்னிக்கவும்: {restaurant} உங்கள் ஆர்டர் {code}-ஐ முடிக்க முடியாது. அதை ரத்து செய்து {amount} திருப்பி அனுப்பினோம்; 3–5 வேலை நாட்களில் தெரியும்."),
        "kn": ("ನಿಮ್ಮ ಆರ್ಡರ್ ರದ್ದಾಗಿದೆ", "ಕ್ಷಮಿಸಿ: {restaurant} ನಿಮ್ಮ ಆರ್ಡರ್ {code} ಪೂರ್ಣಗೊಳಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ. ನಾವು ಅದನ್ನು ರದ್ದುಮಾಡಿ {amount} ನೀವು ಪಾವತಿಸಿದ ರೀತಿಗೆ ಮರುಪಾವತಿಸಿದ್ದೇವೆ; ಸಾಮಾನ್ಯವಾಗಿ 3–5 ಕೆಲಸದ ದಿನಗಳಲ್ಲಿ ಕಾಣುತ್ತದೆ."),
        "mr": ("तुमची ऑर्डर रद्द झाली", "माफ करा: {restaurant} तुमची ऑर्डर {code} पूर्ण करू शकत नाही. आम्ही ती रद्द करून {amount} तुम्ही ज्या प्रकारे पैसे दिले तिथे परत केले आहेत; साधारण 3–5 कामकाजाच्या दिवसांत दिसतात."),
        "bn": ("আপনার অর্ডার বাতিল হয়েছে", "দুঃখিত: {restaurant} আপনার অর্ডার {code} সম্পূর্ণ করতে পারছে না। আমরা এটি বাতিল করে {amount} আপনি যেভাবে পেমেন্ট করেছেন সেখানে ফেরত দিয়েছি; সাধারণত 3–5 কার্যদিবসে দেখা যায়।"),
        "es": ("Tu pedido se canceló", "Lo sentimos: {restaurant} no puede terminar tu pedido {code}. Lo cancelamos y te devolvimos {amount} a tu forma de pago; suele verse en 3–5 días hábiles."),
    },
    "refund_sent": {
        "en": ("Refund sent", "We're sorry about your order {code} from {restaurant}. We've refunded {amount} to how you paid; it usually shows in 3–5 working days."),
        "hi": ("रिफंड भेजा गया", "{restaurant} से आपके ऑर्डर {code} के लिए हमें खेद है। हमने {amount} आपके भुगतान के तरीके में वापस कर दिए हैं; आमतौर पर 3–5 कार्यदिवस में दिखता है।"),
        "te": ("రిఫండ్ పంపాం", "{restaurant} నుండి మీ ఆర్డర్ {code} విషయంలో క్షమించండి. {amount} మీరు చెల్లించిన విధానానికి తిరిగి ఇచ్చాం; సాధారణంగా 3–5 పని దినాల్లో కనిపిస్తుంది."),
        "ta": ("ரீஃபண்ட் அனுப்பப்பட்டது", "{restaurant}-இலிருந்து உங்கள் ஆர்டர் {code}-க்கு வருந்துகிறோம். {amount} நீங்கள் பணம் செலுத்திய வழிக்கே திருப்பி அனுப்பியுள்ளோம்; பொதுவாக 3–5 வேலை நாட்களில் தெரியும்."),
        "kn": ("ಮರುಪಾವತಿ ಕಳುಹಿಸಲಾಗಿದೆ", "{restaurant} ನಿಂದ ನಿಮ್ಮ ಆರ್ಡರ್ {code} ಬಗ್ಗೆ ಕ್ಷಮಿಸಿ. {amount} ನೀವು ಪಾವತಿಸಿದ ರೀತಿಗೆ ಮರುಪಾವತಿಸಿದ್ದೇವೆ; ಸಾಮಾನ್ಯವಾಗಿ 3–5 ಕೆಲಸದ ದಿನಗಳಲ್ಲಿ ಕಾಣುತ್ತದೆ."),
        "mr": ("परतावा पाठवला", "{restaurant} कडील तुमच्या ऑर्डर {code} बद्दल आम्हाला खेद आहे. आम्ही {amount} तुम्ही ज्या प्रकारे पैसे दिले तिथे परत केले आहेत; साधारण 3–5 कामकाजाच्या दिवसांत दिसतात."),
        "bn": ("রিফান্ড পাঠানো হয়েছে", "{restaurant} থেকে আপনার অর্ডার {code}-এর জন্য আমরা দুঃখিত। {amount} আপনি যেভাবে পেমেন্ট করেছেন সেখানে ফেরত দিয়েছি; সাধারণত 3–5 কার্যদিবসে দেখা যায়।"),
        "es": ("Reembolso enviado", "Lamentamos lo de tu pedido {code} de {restaurant}. Te devolvimos {amount} a tu forma de pago; suele verse en 3–5 días hábiles."),
    },
    "delay": {
        "en": ("Your order is running late", "Your order is running late because of a problem on our side. It should arrive by {time}. We're sorry for the wait."),
        "hi": ("आपके ऑर्डर में देर हो रही है", "हमारी तरफ़ की एक समस्या के कारण आपके ऑर्डर में देर हो रही है। यह {time} तक पहुँच जाना चाहिए। इंतज़ार के लिए माफ़ी।"),
        "te": ("మీ ఆర్డర్ ఆలస్యమవుతోంది", "మా వైపు సమస్య వల్ల మీ ఆర్డర్ ఆలస్యమవుతోంది. ఇది {time}కల్లా చేరాలి. వేచి ఉంచినందుకు క్షమించండి."),
        "ta": ("உங்கள் ஆர்டர் தாமதமாகிறது", "எங்கள் பக்கப் பிரச்சினையால் உங்கள் ஆர்டர் தாமதமாகிறது. இது {time}-க்குள் வந்து சேர வேண்டும். காத்திருப்புக்கு மன்னிக்கவும்."),
        "kn": ("ನಿಮ್ಮ ಆರ್ಡರ್ ತಡವಾಗುತ್ತಿದೆ", "ನಮ್ಮ ಕಡೆಯ ಸಮಸ್ಯೆಯಿಂದ ನಿಮ್ಮ ಆರ್ಡರ್ ತಡವಾಗುತ್ತಿದೆ. ಇದು {time} ರೊಳಗೆ ತಲುಪಬೇಕು. ಕಾಯಿಸಿದ್ದಕ್ಕೆ ಕ್ಷಮಿಸಿ."),
        "mr": ("तुमच्या ऑर्डरला उशीर होत आहे", "आमच्या बाजूच्या अडचणीमुळे तुमच्या ऑर्डरला उशीर होत आहे. ती {time} पर्यंत पोहोचली पाहिजे. वाट पाहायला लावल्याबद्दल माफ करा."),
        "bn": ("আপনার অর্ডারে দেরি হচ্ছে", "আমাদের দিকের একটি সমস্যার কারণে আপনার অর্ডারে দেরি হচ্ছে। এটি {time}-এর মধ্যে পৌঁছানোর কথা। অপেক্ষার জন্য দুঃখিত।"),
        "es": ("Tu pedido va con retraso", "Tu pedido va con retraso por un problema de nuestra parte. Debería llegar a las {time}. Sentimos la espera."),
    },
    "area_paused": {
        "en": ("Ordering is paused", "Ordering in {area} is paused for now while we fix a problem. Orders already on their way will still arrive. We'll let you know when we're back."),
        "hi": ("ऑर्डर करना रुका है", "एक समस्या ठीक करने तक {area} में ऑर्डर करना अभी रुका है। जो ऑर्डर रास्ते में हैं वे पहुँचेंगे। वापस आने पर हम बताएँगे।"),
        "te": ("ఆర్డర్లు ఆగాయి", "ఒక సమస్యను సరిచేస్తున్నందున {area}లో ఆర్డర్లు ప్రస్తుతం ఆగాయి. దారిలో ఉన్న ఆర్డర్లు చేరుతాయి. మళ్లీ మొదలవగానే తెలియజేస్తాం."),
        "ta": ("ஆர்டர் செய்வது நிறுத்தப்பட்டுள்ளது", "ஒரு பிரச்சினையைச் சரிசெய்யும் வரை {area}-இல் ஆர்டர் செய்வது தற்போது நிறுத்தப்பட்டுள்ளது. வழியில் உள்ள ஆர்டர்கள் வந்து சேரும். மீண்டும் தொடங்கியதும் தெரிவிப்போம்."),
        "kn": ("ಆರ್ಡರ್ ಮಾಡುವುದು ನಿಂತಿದೆ", "ಸಮಸ್ಯೆಯೊಂದನ್ನು ಸರಿಪಡಿಸುತ್ತಿರುವುದರಿಂದ {area} ನಲ್ಲಿ ಆರ್ಡರ್ ಮಾಡುವುದು ಸದ್ಯಕ್ಕೆ ನಿಂತಿದೆ. ದಾರಿಯಲ್ಲಿರುವ ಆರ್ಡರ್‌ಗಳು ತಲುಪುತ್ತವೆ. ಮತ್ತೆ ಆರಂಭವಾದಾಗ ತಿಳಿಸುತ್ತೇವೆ."),
        "mr": ("ऑर्डर करणे थांबले आहे", "एक अडचण दूर करेपर्यंत {area} मध्ये ऑर्डर करणे सध्या थांबले आहे. वाटेत असलेल्या ऑर्डर पोहोचतील. पुन्हा सुरू झाल्यावर आम्ही कळवू."),
        "bn": ("অর্ডার করা বন্ধ আছে", "একটি সমস্যা ঠিক করা পর্যন্ত {area}-এ অর্ডার করা আপাতত বন্ধ। যে অর্ডারগুলি পথে আছে সেগুলি পৌঁছাবে। আবার চালু হলে আমরা জানাব।"),
        "es": ("Los pedidos están en pausa", "Los pedidos en {area} están en pausa mientras arreglamos un problema. Los pedidos en camino llegarán. Te avisamos cuando volvamos."),
    },
    "area_back": {
        "en": ("We're back", "Ordering in {area} is open again. Thank you for waiting."),
        "hi": ("हम वापस आ गए", "{area} में ऑर्डर करना फिर से शुरू हो गया है। इंतज़ार के लिए धन्यवाद।"),
        "te": ("మళ్లీ వచ్చేశాం", "{area}లో ఆర్డర్లు మళ్లీ మొదలయ్యాయి. వేచి ఉన్నందుకు ధన్యవాదాలు."),
        "ta": ("மீண்டும் வந்துவிட்டோம்", "{area}-இல் மீண்டும் ஆர்டர் செய்யலாம். காத்திருந்ததற்கு நன்றி."),
        "kn": ("ಮತ್ತೆ ಬಂದಿದ್ದೇವೆ", "{area} ನಲ್ಲಿ ಮತ್ತೆ ಆರ್ಡರ್ ಮಾಡಬಹುದು. ಕಾಯ್ದಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು."),
        "mr": ("आम्ही परत आलो", "{area} मध्ये पुन्हा ऑर्डर करता येते. वाट पाहिल्याबद्दल धन्यवाद."),
        "bn": ("আমরা ফিরে এসেছি", "{area}-এ আবার অর্ডার করা যাচ্ছে। অপেক্ষার জন্য ধন্যবাদ।"),
        "es": ("Ya volvimos", "Ya puedes volver a pedir en {area}. Gracias por esperar."),
    },
    "payment_problem": {
        "en": ("Your payment didn't go through", "Your payment didn't go through because of a problem with our payment provider, not your card. You haven't been charged. Please try again in a few minutes."),
        "hi": ("आपका भुगतान नहीं हुआ", "हमारे भुगतान प्रदाता की समस्या के कारण आपका भुगतान नहीं हुआ, आपके कार्ड की वजह से नहीं। आपसे कोई पैसा नहीं लिया गया। कुछ मिनट बाद फिर से कोशिश करें।"),
        "te": ("మీ చెల్లింపు జరగలేదు", "మా చెల్లింపు ప్రొవైడర్ సమస్య వల్ల మీ చెల్లింపు జరగలేదు, మీ కార్డ్ వల్ల కాదు. మీ నుండి డబ్బు తీసుకోలేదు. కొన్ని నిమిషాల తర్వాత మళ్లీ ప్రయత్నించండి."),
        "ta": ("உங்கள் பணம் செலுத்துதல் நடக்கவில்லை", "எங்கள் பணம் செலுத்தும் சேவையின் பிரச்சினையால் உங்கள் பணம் செலுத்துதல் நடக்கவில்லை, உங்கள் கார்டால் அல்ல. உங்களிடம் கட்டணம் வசூலிக்கப்படவில்லை. சில நிமிடங்களில் மீண்டும் முயற்சிக்கவும்."),
        "kn": ("ನಿಮ್ಮ ಪಾವತಿ ಆಗಲಿಲ್ಲ", "ನಮ್ಮ ಪಾವತಿ ಸೇವೆಯ ಸಮಸ್ಯೆಯಿಂದ ನಿಮ್ಮ ಪಾವತಿ ಆಗಲಿಲ್ಲ, ನಿಮ್ಮ ಕಾರ್ಡ್‌ನಿಂದಲ್ಲ. ನಿಮ್ಮಿಂದ ಹಣ ಕಡಿತವಾಗಿಲ್ಲ. ಕೆಲವು ನಿಮಿಷಗಳ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ."),
        "mr": ("तुमचे पेमेंट झाले नाही", "आमच्या पेमेंट सेवेतील अडचणीमुळे तुमचे पेमेंट झाले नाही, तुमच्या कार्डमुळे नाही. तुमच्याकडून पैसे घेतलेले नाहीत. काही मिनिटांनी पुन्हा प्रयत्न करा."),
        "bn": ("আপনার পেমেন্ট হয়নি", "আমাদের পেমেন্ট পরিষেবার একটি সমস্যার কারণে আপনার পেমেন্ট হয়নি, আপনার কার্ডের কারণে নয়। আপনার থেকে টাকা কাটা হয়নি। কয়েক মিনিট পরে আবার চেষ্টা করুন।"),
        "es": ("Tu pago no se completó", "Tu pago no se completó por un problema de nuestro proveedor de pagos, no de tu tarjeta. No se te cobró nada. Inténtalo de nuevo en unos minutos."),
    },
}
# What each template needs: placeholders filled from each order (only with a bulk refund's customers)
# and the ones the admin types in.
INCIDENT_FROM_ORDER = {"restaurant", "code", "amount"}
INCIDENT_ADMIN_PARAMS = {"time"}  # {area} is filled from the recipients' city in Markets (R18)


def incident_placeholders(key: str) -> set[str]:
    import string

    title, body = INCIDENT_MESSAGES[key]["en"]
    return {f for _, f, _, _ in string.Formatter().parse(title + body) if f}


# ── the commission tax invoice to a kitchen (R25, core_api) ───────────────────
# The line for the week's commission, one form for 1 order and one for any other number.
# The invoice is a tax document and is printed in English, like the customer's receipt
# (orders/service/receipt.py); the other languages are here so it can follow the kitchen's
# language once invoices are translated, and so the CI check keeps them complete.
INVOICE_ORDERS: dict[str, tuple[str, str]] = {
    "en": ("Commission on {n} delivered order", "Commission on {n} delivered orders"),
    "hi": ("{n} डिलीवर हुए ऑर्डर पर कमीशन", "{n} डिलीवर हुए ऑर्डर पर कमीशन"),
    "te": ("డెలివర్ అయిన {n} ఆర్డర్‌పై కమీషన్", "డెలివర్ అయిన {n} ఆర్డర్‌లపై కమీషన్"),
    "ta": ("டெலிவரி செய்யப்பட்ட {n} ஆர்டருக்கான கமிஷன்", "டெலிவரி செய்யப்பட்ட {n} ஆர்டர்களுக்கான கமிஷன்"),
    "kn": ("ಡೆಲಿವರಿ ಆದ {n} ಆರ್ಡರ್ ಮೇಲಿನ ಕಮಿಷನ್", "ಡೆಲಿವರಿ ಆದ {n} ಆರ್ಡರ್‌ಗಳ ಮೇಲಿನ ಕಮಿಷನ್"),
    "mr": ("डिलिव्हर झालेल्या {n} ऑर्डरवरील कमिशन", "डिलिव्हर झालेल्या {n} ऑर्डरवरील कमिशन"),
    "bn": ("ডেলিভারি হওয়া {n}টি অর্ডারের কমিশন", "ডেলিভারি হওয়া {n}টি অর্ডারের কমিশন"),
    "es": ("Comisión por {n} pedido entregado", "Comisión por {n} pedidos entregados"),
}


def invoice_orders_line(n: int, language: str = "en") -> str:
    """"Commission on 1 delivered order" / "Commission on 2 delivered orders" in ``language``."""
    one, other = INVOICE_ORDERS.get(language) or INVOICE_ORDERS["en"]
    return (one if n == 1 else other).format(n=n)


def entries() -> dict[str, dict[str, str]]:
    """Every text here as "<name>" → {language: text}, for the CI check."""
    out: dict[str, dict[str, str]] = {}
    for side, presets in QUICK_PRESETS.items():
        for key, texts in presets.items():
            out[f"chat.{side}.{key}"] = texts
    for key, texts in NAMES.items():
        out[f"names.{key}"] = texts
    out["otp_sms"] = OTP_SMS
    for key, texts in BILL_LINES.items():
        out[f"bill.{key}"] = texts
    for key, texts in WELCOME.items():
        out[f"welcome.{key}"] = texts
    for key, texts in AUTH_EMAILS.items():
        out[f"auth_email.{key}"] = texts
    for key, texts in KITCHEN_APPLIED.items():
        out[f"kitchen_applied.{key}"] = texts
    for key, texts in DELIVERY_SIGN_UP.items():
        out[f"delivery_sign_up.{key}"] = texts
    out["invoice_orders.one"] = {lang: t[0] for lang, t in INVOICE_ORDERS.items()}
    out["invoice_orders.other"] = {lang: t[1] for lang, t in INVOICE_ORDERS.items()}
    return out
