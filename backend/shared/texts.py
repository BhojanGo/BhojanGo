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
    for key, texts in AUTH_EMAILS.items():
        out[f"auth_email.{key}"] = texts
    return out
