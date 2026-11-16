"""What BhojanGo says, in every language a country lists in Markets (P15, round 5).

Voice (brand board): plain, specific, warm. Numbers over adjectives: say the
time, the amount, the name. Never blame the customer, the rider or the kitchen.
No emoji.

Each message has a push title and a body; SMS sends "BhojanGo: <body>" and
email wraps the same words in the brand layout. India SMS must use a
DLT-registered template per message and language: the key is
"<message>_<language>" (e.g. "order_picked_up_hi", "order_picked_up_ta") and its
variables are the placeholders below, in the order they appear
(MSG91_TEMPLATE_IDS maps keys to template ids; README "Messages" lists them).

Languages: shared/texts.py LANGUAGES (en, hi, te, ta, kn, mr, bn, es). English is
the source; the others are machine translations listed in
packages/i18n/REVIEW.md ("Backend messages"). ``python tools/i18n/check_locales.py``
(make ci-i18n) fails if a text lacks a language that a live country lists.

Stdlib, shared.texts and shared.money only: the CI check imports this file without the
worker's packages.
"""
import html
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from shared.money import format_money
from shared.texts import LANGUAGES, fallback_name, language_for, preset_text

__all__ = ["LANGUAGES", "language_for"]

# "Arriving around 8:24 PM." — omitted when there's no estimate.
ARRIVING = {
    "en": "Arriving around {eta}.",
    "hi": "लगभग {eta} तक पहुंचेगा।",
    "te": "సుమారు {eta}కి చేరుతుంది.",
    "ta": "சுமார் {eta}க்கு வந்து சேரும்.",
    "kn": "ಸುಮಾರು {eta}ಕ್ಕೆ ತಲುಪುತ್ತದೆ.",
    "mr": "साधारण {eta} पर्यंत पोहोचेल.",
    "bn": "আনুমানিক {eta}-এর মধ্যে পৌঁছাবে।",
    "es": "Llega alrededor de las {eta}.",
}

# Messages whose body is someone's own words (a quick message, B2): only the
# title is translated, and a preset quick message is shown in the reader's language.
VERBATIM = frozenset({"order_message"})

# (title, body) per message per language.
CATALOGUE: dict[str, dict[str, tuple[str, str]]] = {
    "order_placed": {
        "en": ("Order placed", "{restaurant} has your order {code}. We'll tell you when they start cooking."),
        "hi": ("ऑर्डर मिल गया", "{restaurant} को आपका ऑर्डर {code} मिल गया है। खाना बनना शुरू होते ही हम बताएंगे।"),
        "te": ("ఆర్డర్ అందింది", "{restaurant}కి మీ ఆర్డర్ {code} అందింది. వంట మొదలవగానే మీకు తెలియజేస్తాం."),
        "ta": ("ஆர்டர் பெறப்பட்டது", "{restaurant} உங்கள் ஆர்டர் {code}-ஐப் பெற்றுள்ளது. சமையல் தொடங்கியதும் தெரிவிப்போம்."),
        "kn": ("ಆರ್ಡರ್ ತಲುಪಿದೆ", "{restaurant}ಗೆ ನಿಮ್ಮ ಆರ್ಡರ್ {code} ತಲುಪಿದೆ. ಅಡುಗೆ ಶುರುವಾದ ತಕ್ಷಣ ತಿಳಿಸುತ್ತೇವೆ."),
        "mr": ("ऑर्डर मिळाली", "{restaurant} ला तुमची ऑर्डर {code} मिळाली आहे. स्वयंपाक सुरू होताच आम्ही कळवू."),
        "bn": ("অর্ডার পৌঁছেছে", "{restaurant} আপনার অর্ডার {code} পেয়েছে। রান্না শুরু হলেই আমরা জানাব।"),
        "es": ("Pedido recibido", "{restaurant} tiene tu pedido {code}. Te avisamos cuando empiecen a cocinar."),
    },
    "order_accepted": {
        "en": ("Order accepted", "{restaurant} accepted your order. {arriving}"),
        "hi": ("ऑर्डर स्वीकार हुआ", "{restaurant} ने आपका ऑर्डर स्वीकार कर लिया। {arriving}"),
        "te": ("ఆర్డర్ అంగీకరించారు", "{restaurant} మీ ఆర్డర్‌ను అంగీకరించింది. {arriving}"),
        "ta": ("ஆர்டர் ஏற்கப்பட்டது", "{restaurant} உங்கள் ஆர்டரை ஏற்றுக்கொண்டது. {arriving}"),
        "kn": ("ಆರ್ಡರ್ ಸ್ವೀಕರಿಸಲಾಗಿದೆ", "{restaurant} ನಿಮ್ಮ ಆರ್ಡರ್ ಸ್ವೀಕರಿಸಿದೆ. {arriving}"),
        "mr": ("ऑर्डर स्वीकारली", "{restaurant} ने तुमची ऑर्डर स्वीकारली. {arriving}"),
        "bn": ("অর্ডার গ্রহণ করা হয়েছে", "{restaurant} আপনার অর্ডার গ্রহণ করেছে। {arriving}"),
        "es": ("Pedido aceptado", "{restaurant} aceptó tu pedido. {arriving}"),
    },
    "order_preparing": {
        "en": ("Cooking now", "{restaurant} is cooking your order. {arriving}"),
        "hi": ("खाना बन रहा है", "{restaurant} आपका ऑर्डर बना रहा है। {arriving}"),
        "te": ("వంట జరుగుతోంది", "{restaurant} మీ ఆర్డర్‌ను వండుతోంది. {arriving}"),
        "ta": ("சமையல் நடக்கிறது", "{restaurant} உங்கள் ஆர்டரைச் சமைக்கிறது. {arriving}"),
        "kn": ("ಅಡುಗೆ ನಡೆಯುತ್ತಿದೆ", "{restaurant} ನಿಮ್ಮ ಆರ್ಡರ್ ಅಡುಗೆ ಮಾಡುತ್ತಿದೆ. {arriving}"),
        "mr": ("स्वयंपाक सुरू आहे", "{restaurant} तुमची ऑर्डर बनवत आहे. {arriving}"),
        "bn": ("রান্না চলছে", "{restaurant} আপনার অর্ডার রান্না করছে। {arriving}"),
        "es": ("Cocinando", "{restaurant} está cocinando tu pedido. {arriving}"),
    },
    "driver_assigned": {
        "en": ("Delivery partner on the way to the kitchen", "{rider} will bring your order from {restaurant}. {arriving}"),
        "hi": ("डिलीवरी पार्टनर तय हो गया", "{rider} {restaurant} से आपका ऑर्डर लाएंगे। {arriving}"),
        "te": ("డెలివరీ పార్ట్‌నర్ ఖరారయ్యారు", "{rider} {restaurant} నుండి మీ ఆర్డర్ తెస్తారు. {arriving}"),
        "ta": ("டெலிவரி பார்ட்னர் உறுதியானார்", "{rider} {restaurant}-இலிருந்து உங்கள் ஆர்டரைக் கொண்டு வருவார். {arriving}"),
        "kn": ("ಡೆಲಿವರಿ ಪಾರ್ಟ್ನರ್ ನಿಗದಿಯಾಗಿದ್ದಾರೆ", "{rider} {restaurant}ನಿಂದ ನಿಮ್ಮ ಆರ್ಡರ್ ತರುತ್ತಾರೆ. {arriving}"),
        "mr": ("डिलिव्हरी पार्टनर ठरला", "{rider} {restaurant} मधून तुमची ऑर्डर आणतील. {arriving}"),
        "bn": ("ডেলিভারি পার্টনার ঠিক হয়েছে", "{rider} {restaurant} থেকে আপনার অর্ডার নিয়ে আসবেন। {arriving}"),
        "es": ("Repartidor en camino a la cocina", "{rider} llevará tu pedido de {restaurant}. {arriving}"),
    },
    "order_picked_up": {
        "en": ("On the way", "{rider} picked up your order and is heading to you. {arriving}"),
        "hi": ("रास्ते में है", "{rider} ने आपका ऑर्डर ले लिया है और आपके पास आ रहे हैं। {arriving}"),
        "te": ("దారిలో ఉంది", "{rider} మీ ఆర్డర్ తీసుకుని మీ వద్దకు వస్తున్నారు. {arriving}"),
        "ta": ("வழியில் உள்ளது", "{rider} உங்கள் ஆர்டரை எடுத்துக்கொண்டு உங்களிடம் வருகிறார். {arriving}"),
        "kn": ("ದಾರಿಯಲ್ಲಿದೆ", "{rider} ನಿಮ್ಮ ಆರ್ಡರ್ ತೆಗೆದುಕೊಂಡು ನಿಮ್ಮ ಬಳಿ ಬರುತ್ತಿದ್ದಾರೆ. {arriving}"),
        "mr": ("वाटेत आहे", "{rider} तुमची ऑर्डर घेऊन तुमच्याकडे येत आहेत. {arriving}"),
        "bn": ("পথে আছে", "{rider} আপনার অর্ডার নিয়ে আপনার কাছে আসছেন। {arriving}"),
        "es": ("En camino", "{rider} recogió tu pedido y va hacia ti. {arriving}"),
    },
    "order_almost_there": {
        "en": ("Almost there", "{rider} is a couple of minutes away with your order from {restaurant}."),
        "hi": ("बस पहुंचने वाले हैं", "{rider} {restaurant} से आपका ऑर्डर लेकर बस कुछ मिनट दूर हैं।"),
        "te": ("దాదాపు వచ్చేశారు", "{rider} {restaurant} నుండి మీ ఆర్డర్‌తో కొన్ని నిమిషాల దూరంలో ఉన్నారు."),
        "ta": ("கிட்டத்தட்ட வந்துவிட்டார்", "{restaurant}-இலிருந்து உங்கள் ஆர்டருடன் {rider} இரண்டு நிமிடத் தொலைவில் இருக்கிறார்."),
        "kn": ("ಬಹುತೇಕ ತಲುಪಿದ್ದಾರೆ", "{restaurant}ನಿಂದ ನಿಮ್ಮ ಆರ್ಡರ್‌ನೊಂದಿಗೆ {rider} ಎರಡು ನಿಮಿಷದ ದೂರದಲ್ಲಿದ್ದಾರೆ."),
        "mr": ("जवळजवळ पोहोचले", "{rider} {restaurant} मधील तुमची ऑर्डर घेऊन फक्त काही मिनिटांच्या अंतरावर आहेत."),
        "bn": ("প্রায় পৌঁছে গেছেন", "{rider} {restaurant} থেকে আপনার অর্ডার নিয়ে আর মাত্র কয়েক মিনিট দূরে।"),
        "es": ("Ya casi llega", "{rider} está a un par de minutos con tu pedido de {restaurant}."),
    },
    "order_message": {
        "en": ("Message from {name}", "{text}"),
        "hi": ("{name} का संदेश", "{text}"),
        "te": ("{name} నుండి సందేశం", "{text}"),
        "ta": ("{name} அனுப்பிய செய்தி", "{text}"),
        "kn": ("{name} ಅವರಿಂದ ಸಂದೇಶ", "{text}"),
        "mr": ("{name} यांचा संदेश", "{text}"),
        "bn": ("{name}-এর বার্তা", "{text}"),
        "es": ("Mensaje de {name}", "{text}"),
    },
    "order_delivered": {
        "en": ("Delivered", "Your order from {restaurant} is here. Enjoy your meal."),
        "hi": ("डिलीवर हो गया", "{restaurant} से आपका ऑर्डर पहुंच गया है। खाने का आनंद लें।"),
        "te": ("డెలివరీ అయింది", "{restaurant} నుండి మీ ఆర్డర్ చేరింది. హాయిగా ఆస్వాదించండి."),
        "ta": ("டெலிவரி செய்யப்பட்டது", "{restaurant}-இலிருந்து உங்கள் ஆர்டர் வந்துவிட்டது. சுவைத்து மகிழுங்கள்."),
        "kn": ("ಡೆಲಿವರಿ ಆಗಿದೆ", "{restaurant}ನಿಂದ ನಿಮ್ಮ ಆರ್ಡರ್ ತಲುಪಿದೆ. ಊಟವನ್ನು ಆನಂದಿಸಿ."),
        "mr": ("डिलिव्हर झाली", "{restaurant} मधून तुमची ऑर्डर पोहोचली आहे. जेवणाचा आनंद घ्या."),
        "bn": ("ডেলিভারি হয়েছে", "{restaurant} থেকে আপনার অর্ডার পৌঁছে গেছে। খাবার উপভোগ করুন।"),
        "es": ("Entregado", "Tu pedido de {restaurant} ya llegó. Buen provecho."),
    },
    "order_cancelled_refunded": {
        "en": ("Order cancelled", "Your order {code} from {restaurant} was cancelled. {refund} is on its way back to you; banks usually take 5–7 days."),
        "hi": ("ऑर्डर रद्द हुआ", "{restaurant} से आपका ऑर्डर {code} रद्द हो गया। {refund} आपको वापस भेजे जा रहे हैं; बैंक में आमतौर पर 5–7 दिन लगते हैं।"),
        "te": ("ఆర్డర్ రద్దయింది", "{restaurant} నుండి మీ ఆర్డర్ {code} రద్దయింది. {refund} మీకు తిరిగి పంపుతున్నాం; బ్యాంకుకు సాధారణంగా 5–7 రోజులు పడుతుంది."),
        "ta": ("ஆர்டர் ரத்தானது", "{restaurant} ஆர்டர் {code} ரத்தானது. {refund} திருப்பி அனுப்பப்படுகிறது; வங்கிகள் பொதுவாக 5–7 நாட்கள் எடுக்கும்."),
        "kn": ("ಆರ್ಡರ್ ರದ್ದಾಗಿದೆ", "{restaurant}ನಿಂದ ನಿಮ್ಮ ಆರ್ಡರ್ {code} ರದ್ದಾಗಿದೆ. {refund} ಹಿಂದಿರುಗಿಸಲಾಗುತ್ತಿದೆ; ಬ್ಯಾಂಕ್‌ಗಳು ಸಾಮಾನ್ಯವಾಗಿ 5–7 ದಿನ ತೆಗೆದುಕೊಳ್ಳುತ್ತವೆ."),
        "mr": ("ऑर्डर रद्द झाली", "{restaurant} मधील तुमची ऑर्डर {code} रद्द झाली. {refund} तुम्हाला परत पाठवले जात आहेत; बँकांना साधारणपणे 5–7 दिवस लागतात."),
        "bn": ("অর্ডার বাতিল হয়েছে", "{restaurant} থেকে আপনার অর্ডার {code} বাতিল হয়েছে। {refund} আপনাকে ফেরত পাঠানো হচ্ছে; ব্যাংকে সাধারণত ৫–৭ দিন লাগে।"),
        "es": ("Pedido cancelado", "Tu pedido {code} de {restaurant} se canceló. Te estamos devolviendo {refund}; los bancos suelen tardar de 5 a 7 días."),
    },
    "order_cancelled_unpaid": {
        "en": ("Order cancelled", "Your order {code} from {restaurant} was cancelled. You have not been charged."),
        "hi": ("ऑर्डर रद्द हुआ", "{restaurant} से आपका ऑर्डर {code} रद्द हो गया। आपसे कोई पैसा नहीं लिया गया।"),
        "te": ("ఆర్డర్ రద్దయింది", "{restaurant} నుండి మీ ఆర్డర్ {code} రద్దయింది. మీ నుండి డబ్బు తీసుకోలేదు."),
        "ta": ("ஆர்டர் ரத்தானது", "{restaurant} ஆர்டர் {code} ரத்தானது. உங்களிடம் கட்டணம் எதுவும் வசூலிக்கப்படவில்லை."),
        "kn": ("ಆರ್ಡರ್ ರದ್ದಾಗಿದೆ", "{restaurant}ನಿಂದ ನಿಮ್ಮ ಆರ್ಡರ್ {code} ರದ್ದಾಗಿದೆ. ನಿಮ್ಮಿಂದ ಯಾವುದೇ ಹಣ ಪಡೆದಿಲ್ಲ."),
        "mr": ("ऑर्डर रद्द झाली", "{restaurant} मधील तुमची ऑर्डर {code} रद्द झाली. तुमच्याकडून कोणतेही पैसे घेतलेले नाहीत."),
        "bn": ("অর্ডার বাতিল হয়েছে", "{restaurant} থেকে আপনার অর্ডার {code} বাতিল হয়েছে। আপনার কাছ থেকে কোনো টাকা নেওয়া হয়নি।"),
        "es": ("Pedido cancelado", "Tu pedido {code} de {restaurant} se canceló. No se te cobró nada."),
    },
    "payment_failed": {
        "en": ("Payment didn't go through", "Payment didn't go through. You have not been charged. Your order {code} is held for a few minutes; try again in the app."),
        "hi": ("भुगतान नहीं हुआ", "भुगतान नहीं हो पाया। आपसे पैसा नहीं लिया गया। आपका ऑर्डर {code} कुछ मिनट के लिए रखा है; ऐप में फिर से कोशिश करें।"),
        "te": ("చెల్లింపు జరగలేదు", "చెల్లింపు జరగలేదు. మీ నుండి డబ్బు తీసుకోలేదు. మీ ఆర్డర్ {code} కొన్ని నిమిషాలు ఉంచాం; యాప్‌లో మళ్లీ ప్రయత్నించండి."),
        "ta": ("பணம் செலுத்தப்படவில்லை", "பணம் செலுத்தப்படவில்லை, கட்டணம் வசூலிக்கப்படவில்லை. ஆர்டர் {code} சில நிமிடங்கள் வைக்கப்பட்டுள்ளது; ஆப்பில் மீண்டும் முயலுங்கள்."),
        "kn": ("ಪಾವತಿ ಆಗಲಿಲ್ಲ", "ಪಾವತಿ ಆಗಲಿಲ್ಲ. ನಿಮ್ಮಿಂದ ಹಣ ಪಡೆದಿಲ್ಲ. ನಿಮ್ಮ ಆರ್ಡರ್ {code} ಕೆಲವು ನಿಮಿಷ ಕಾಯ್ದಿರಿಸಲಾಗಿದೆ; ಆ್ಯಪ್‌ನಲ್ಲಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ."),
        "mr": ("पेमेंट झाले नाही", "पेमेंट झाले नाही. तुमच्याकडून पैसे घेतलेले नाहीत. तुमची ऑर्डर {code} काही मिनिटांसाठी राखून ठेवली आहे; ॲपमध्ये पुन्हा प्रयत्न करा."),
        "bn": ("পেমেন্ট হয়নি", "পেমেন্ট হয়নি। আপনার কাছ থেকে টাকা নেওয়া হয়নি। আপনার অর্ডার {code} কয়েক মিনিট রাখা আছে; অ্যাপে আবার চেষ্টা করুন।"),
        "es": ("No se pudo cobrar", "No se pudo procesar el pago. No se te cobró nada. Guardamos tu pedido {code} unos minutos; vuelve a intentarlo en la app."),
    },
    "refund_items": {
        "en": ("Refund sent", "{amount} refunded for order {code}. Banks usually take 5–7 days."),
        "hi": ("रिफंड भेजा गया", "ऑर्डर {code} के लिए {amount} रिफंड किए गए। बैंक में आमतौर पर 5–7 दिन लगते हैं।"),
        "te": ("రిఫండ్ పంపాం", "ఆర్డర్ {code}కి {amount} రిఫండ్ చేశాం. బ్యాంకుకు సాధారణంగా 5–7 రోజులు పడుతుంది."),
        "ta": ("ரீஃபண்ட் அனுப்பப்பட்டது", "ஆர்டர் {code}-க்கு {amount} ரீஃபண்ட் செய்யப்பட்டது. வங்கிகள் பொதுவாக 5–7 நாட்கள் எடுக்கும்."),
        "kn": ("ರೀಫಂಡ್ ಕಳುಹಿಸಲಾಗಿದೆ", "ಆರ್ಡರ್ {code}ಗೆ {amount} ರೀಫಂಡ್ ಮಾಡಲಾಗಿದೆ. ಬ್ಯಾಂಕ್‌ಗಳು ಸಾಮಾನ್ಯವಾಗಿ 5–7 ದಿನ ತೆಗೆದುಕೊಳ್ಳುತ್ತವೆ."),
        "mr": ("रिफंड पाठवला", "ऑर्डर {code} साठी {amount} रिफंड केले. बँकांना साधारणपणे 5–7 दिवस लागतात."),
        "bn": ("রিফান্ড পাঠানো হয়েছে", "অর্ডার {code}-এর জন্য {amount} রিফান্ড করা হয়েছে। ব্যাংকে সাধারণত ৫–৭ দিন লাগে।"),
        "es": ("Reembolso enviado", "Reembolsamos {amount} del pedido {code}. Los bancos suelen tardar de 5 a 7 días."),
    },
    "partner_new_order": {
        "en": ("New order {code}", "{items}, {total}. Accept by {accept_by}."),
        "hi": ("नया ऑर्डर {code}", "{items}, {total}। {accept_by} तक स्वीकार करें।"),
        "te": ("కొత్త ఆర్డర్ {code}", "{items}, {total}. {accept_by} లోపు అంగీకరించండి."),
        "ta": ("புதிய ஆர்டர் {code}", "{items}, {total}. {accept_by}-க்குள் ஏற்றுக்கொள்ளுங்கள்."),
        "kn": ("ಹೊಸ ಆರ್ಡರ್ {code}", "{items}, {total}. {accept_by} ಒಳಗೆ ಸ್ವೀಕರಿಸಿ."),
        "mr": ("नवीन ऑर्डर {code}", "{items}, {total}. {accept_by} पर्यंत स्वीकारा."),
        "bn": ("নতুন অর্ডার {code}", "{items}, {total}। {accept_by}-এর মধ্যে গ্রহণ করুন।"),
        "es": ("Nuevo pedido {code}", "{items}, {total}. Acéptalo antes de las {accept_by}."),
    },
    "payout_paid": {
        "en": ("Payout sent", "{amount} sent to your bank account for {period}."),
        "hi": ("भुगतान भेजा गया", "{period} के लिए {amount} आपके बैंक खाते में भेजे गए।"),
        "te": ("చెల్లింపు పంపాం", "{period}కి {amount} మీ బ్యాంక్ ఖాతాకు పంపాం."),
        "ta": ("பணம் அனுப்பப்பட்டது", "{period}-க்கான {amount} உங்கள் வங்கிக் கணக்குக்கு அனுப்பப்பட்டது."),
        "kn": ("ಪಾವತಿ ಕಳುಹಿಸಲಾಗಿದೆ", "{period}ಗಾಗಿ {amount} ನಿಮ್ಮ ಬ್ಯಾಂಕ್ ಖಾತೆಗೆ ಕಳುಹಿಸಲಾಗಿದೆ."),
        "mr": ("पेआउट पाठवले", "{period} साठी {amount} तुमच्या बँक खात्यात पाठवले."),
        "bn": ("পেআউট পাঠানো হয়েছে", "{period}-এর জন্য {amount} আপনার ব্যাংক অ্যাকাউন্টে পাঠানো হয়েছে।"),
        "es": ("Pago enviado", "Enviamos {amount} a tu cuenta bancaria por {period}."),
    },
}

# "1 item" / "3 items"
ITEMS = {
    "en": ("{n} item", "{n} items"),
    "hi": ("{n} आइटम", "{n} आइटम"),
    "te": ("{n} ఐటమ్", "{n} ఐటమ్స్"),
    "ta": ("{n} பொருள்", "{n} பொருட்கள்"),
    "kn": ("{n} ಐಟಂ", "{n} ಐಟಂಗಳು"),
    "mr": ("{n} आयटम", "{n} आयटम"),
    "bn": ("{n}টি আইটেম", "{n}টি আইটেম"),
    "es": ("{n} artículo", "{n} artículos"),
}

EMAIL_FOOTER = {
    "en": "BhojanGo · The honest table. These emails are about your BhojanGo orders.",
    "hi": "BhojanGo · असली खाना, सच्चा दाम। ये ईमेल आपके ऑर्डर के बारे में हैं।",
    "te": "BhojanGo · అసలైన రుచి, న్యాయమైన ధర. ఈ ఈమెయిల్స్ మీ ఆర్డర్‌ల గురించి.",
    "ta": "BhojanGo · உண்மையான உணவு, நியாயமான விலை. இந்த மின்னஞ்சல்கள் உங்கள் BhojanGo ஆர்டர்கள் பற்றியவை.",
    "kn": "BhojanGo · ನಿಜವಾದ ಊಟ, ನ್ಯಾಯಯುತ ಬೆಲೆ. ಈ ಇಮೇಲ್‌ಗಳು ನಿಮ್ಮ BhojanGo ಆರ್ಡರ್‌ಗಳ ಬಗ್ಗೆ.",
    "mr": "BhojanGo · खरं जेवण, योग्य किंमत. हे ईमेल तुमच्या BhojanGo ऑर्डरबद्दल आहेत.",
    "bn": "BhojanGo · আসল খাবার, ন্যায্য দাম। এই ইমেলগুলি আপনার BhojanGo অর্ডার নিয়ে।",
    "es": "BhojanGo · La mesa honesta. Estos correos son sobre tus pedidos de BhojanGo.",
}
EMAIL_TOTAL = {"en": "Total", "hi": "कुल", "te": "మొత్తం", "ta": "மொத்தம்", "kn": "ಒಟ್ಟು", "mr": "एकूण",
               "bn": "মোট", "es": "Total"}
EMAIL_ORDER = {"en": "Order", "hi": "ऑर्डर", "te": "ఆర్డర్", "ta": "ஆர்டர்", "kn": "ಆರ್ಡರ್", "mr": "ऑर्डर",
               "bn": "অর্ডার", "es": "Pedido"}


def entries() -> dict[str, dict[str, str]]:
    """Every text here as "<name>" → {language: text}, for the CI check (tools/i18n)."""
    out: dict[str, dict[str, str]] = {}
    for key, texts in CATALOGUE.items():
        out[f"{key}.title"] = {lang: t[0] for lang, t in texts.items()}
        out[f"{key}.body"] = {lang: t[1] for lang, t in texts.items()}
    out["arriving"] = ARRIVING
    out["items.one"] = {lang: t[0] for lang, t in ITEMS.items()}
    out["items.other"] = {lang: t[1] for lang, t in ITEMS.items()}
    out["email.footer"], out["email.total"], out["email.order"] = EMAIL_FOOTER, EMAIL_TOTAL, EMAIL_ORDER
    return out


@dataclass(frozen=True)
class Rendered:
    key: str
    language: str
    title: str
    body: str
    params: dict[str, str]  # the placeholder values (DLT variables)

    @property
    def sms(self) -> str:
        return f"BhojanGo: {self.body}"

    @property
    def dlt_template(self) -> str:
        return f"{self.key}_{self.language}"


def render(key: str, language: str, **params: object) -> Rendered:
    """Fill a message. ``eta`` (a formatted time) becomes the "Arriving around"
    sentence; without it the sentence is left out. A missing ``rider`` name reads
    "Your delivery partner" in the language. A quick message (``order_message``) sent as a
    ``preset`` by ``from_role`` is shown in the reader's language; free text as written."""
    language = language if language in LANGUAGES else "en"
    texts = CATALOGUE[key]
    title, body = texts.get(language, texts["en"])
    values = {k: str(v) for k, v in params.items() if v is not None and v != ""}
    if isinstance(params.get("items"), int):
        one, many = ITEMS.get(language, ITEMS["en"])
        values["items"] = (one if params["items"] == 1 else many).format(n=params["items"])
    eta = values.get("eta")
    values["arriving"] = ARRIVING.get(language, ARRIVING["en"]).format(eta=eta) if eta else ""
    if not values.get("rider"):
        values["rider"] = fallback_name("rider", language)
    if key == "order_message":
        side = values.get("from_role", "")
        values["text"] = preset_text(side, values.get("preset"), language) or values.get("text", "")
        if not values.get("name"):
            values["name"] = fallback_name(side, language)
    used = {k: values.get(k, "") for k in _placeholders(title + body)}
    filled_title, filled_body = title.format(**used), body.format(**used)
    return Rendered(key, language, filled_title.strip(), " ".join(filled_body.split()), used)


def _placeholders(text: str) -> list[str]:
    import string

    return [f for _, f, _, _ in string.Formatter().parse(text) if f]


# ── formatting ────────────────────────────────────────────────────────────────

def money(amount: Decimal | float | str, currency: str) -> str:
    """₹1,24,050.00 (Indian grouping) or $1,240.50: the one backend formatter (shared.money)."""
    return format_money(amount, currency)


def minor_to_money(minor: int | str, currency: str) -> str:
    return money(Decimal(int(minor)) / 100, currency)


def clock(at: datetime | str | None, timezone: str) -> str | None:
    """8:24 PM in the city's time."""
    if not at:
        return None
    when = datetime.fromisoformat(at) if isinstance(at, str) else at
    local = when.astimezone(ZoneInfo(timezone))
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"


def order_code(order_id: str) -> str:
    return "#" + order_id.replace("-", "")[:6].upper()


def period(start: date, end_exclusive: date) -> str:
    """3–9 Nov (the run's end date is exclusive)."""
    from datetime import timedelta

    last = end_exclusive - timedelta(days=1)
    if start.month == last.month:
        return f"{start.day}–{last.day} {last.strftime('%b')}"
    return f"{start.day} {start.strftime('%b')} – {last.day} {last.strftime('%b')}"


def email_html(r: Rendered, *, total: str | None = None, code: str | None = None) -> str:
    """The brand email: Peacock heading, the message, an optional total line."""
    esc = html.escape
    rows = ""
    if total:
        rows = (f'<tr><td style="padding:12px 0 0;color:#3D4A4E">{esc(EMAIL_ORDER[r.language])} {esc(code or "")}</td>'
                f'<td style="padding:12px 0 0;text-align:right;font-weight:700">{esc(EMAIL_TOTAL[r.language])} {esc(total)}</td></tr>')
    return f"""<!doctype html><html lang="{r.language}"><body style="margin:0;background:#F4F6F6">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F6F6;padding:24px 12px">
<tr><td align="center"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"
 style="max-width:520px;background:#FFFFFF;border-radius:16px;padding:28px;font-family:Inter,
 'Noto Sans Devanagari','Noto Sans Telugu','Noto Sans Tamil','Noto Sans Kannada','Noto Sans Bengali',Arial,sans-serif;color:#111418">
<tr><td colspan="2" style="font-size:20px;font-weight:700;color:#0B5D66;padding-bottom:16px">bhojango</td></tr>
<tr><td colspan="2" style="font-size:24px;font-weight:700;padding-bottom:8px">{esc(r.title)}</td></tr>
<tr><td colspan="2" style="font-size:16px;line-height:1.5">{esc(r.body)}</td></tr>
{rows}
<tr><td colspan="2" style="font-size:13px;color:#3D4A4E;padding-top:24px">{esc(EMAIL_FOOTER[r.language])}</td></tr>
</table></td></tr></table></body></html>"""
