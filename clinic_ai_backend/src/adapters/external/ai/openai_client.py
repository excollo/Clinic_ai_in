"""OpenAI client module."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib import error
from urllib import request

from src.core.config import get_settings
from src.core.language_support import normalize_intake_language


# Canonical intake taxonomy.
# Keep this list as the single source of truth for topic keys used across
# ALLOWED_TOPICS and TOPIC_QUESTION_TEMPLATES to prevent prompt/backend drift.
CANONICAL_INTAKE_TOPICS = (
    "reason_for_visit",
    "onset_duration",
    "severity_progression",
    "associated_symptoms",
    "red_flag_check",
    "impact_daily_life",
    "current_medications",
    "past_medical_history",
    "treatment_history",
    "recurrence_status",
    "family_history",
    "trigger_cause",
    "travel_history",
    "pain_assessment",
    "past_evaluation",
    "menstrual_pregnancy",
    "allergies",
    "closing",
)
ALLOWED_TOPICS = set(CANONICAL_INTAKE_TOPICS)

# Backward-compat aliases for historic prompt/model keys.
# This allows old payloads to keep working while we migrate all producers to the
# canonical taxonomy above.
TOPIC_KEY_ALIASES = {
    "onset_duration_or_trigger": "onset_duration",
    "current_symptoms": "associated_symptoms",
    "pain_discomfort": "pain_assessment",
    "temporal_pattern": "severity_progression",
    "additional_information": "closing",
    "final_check": "closing",
}
INTAKE_VALIDATION_REASON_CODES = {
    "missing_required_key",
    "invalid_type",
    "missing_agent_block",
    "invalid_topic",
}
MESSAGE_VALIDATION_REASON_CODES = {
    "empty_message",
    "too_long",
    "not_question_format",
    "low_information_prompt",
    "language_mismatch",
}


class IntakeTurnError(RuntimeError):
    """Structured intake generation failure used by service-level fallback routing."""

    def __init__(
        self,
        reason_code: str,
        *,
        model_topic: str = "",
        selected_topic: str = "",
    ) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.model_topic = model_topic
        self.selected_topic = selected_topic

CHRONIC_KEYWORDS = {
    "diabetes",
    "thyroid",
    "hypertension",
    "blood pressure",
    "high bp",
    "high sugar",
    "asthma",
    "arthritis",
    "migraine",
    "pcos",
    "pcod",
    "cancer",
}
HEREDITARY_KEYWORDS = {"family history", "genetic", "runs in family", "inherited"}
ALLERGY_KEYWORDS = {"allergy", "allergic", "rash", "hives", "itching", "reaction"}
PAIN_KEYWORDS = {
    "pain",
    "ache",
    "aching",
    "cramp",
    "burning",
    "stabbing",
    "back pain",
    "chest pain",
    "abdominal pain",
    "pelvic pain",
    "headache",
}
WOMENS_HEALTH_KEYWORDS = {
    "period",
    "periods",
    "pregnan",
    "menstrual",
    "bleeding",
    "pelvic pain",
    "vaginal",
    "white discharge",
    "fibroid",
    "ovary",
    "ovarian",
    "uterus",
    "lower abdominal pain",
    "abdominal pain",
    "stomach pain",
}

TOPIC_QUESTION_TEMPLATES = {
    "en": {
        "reason_for_visit": "Please tell me the main health issue you want to discuss today?",
        "onset_duration": "When did this problem first start, and roughly how long has it lasted?",
        "severity_progression": "What makes it better or worse, like time of day, food, or activity?",
        "associated_symptoms": "What other symptoms have you noticed along with this problem, and how have they been affecting you?",
        "red_flag_check": "Please describe any serious warning signs you've noticed, such as severe pain, breathlessness, fainting, bleeding, or sudden worsening?",
        "impact_daily_life": "How is this issue affecting your daily routine, such as sleep, eating, work, movement, or energy?",
        "current_medications": "What medicines, supplements, or home remedies are you currently taking for this, including anything you started recently?",
        "past_medical_history": "Please describe any past medical conditions, surgeries, or major illnesses that may be related to this problem?",
        "treatment_history": "What treatment or medical care have you already received for this problem so far?",
        "recurrence_status": "Please describe whether this is a new problem, a recurrence, or a follow-up of an older diagnosis?",
        "family_history": "Please describe any similar or related health problems in your close family, such as parents or siblings?",
        "trigger_cause": "Did anything happen around the time this started, such as travel, food changes, injury, infection exposure, or stress?",
        "travel_history": "Please describe any recent travel you have had, including where you went, when you traveled, and whether symptoms started during or after the trip?",
        "pain_assessment": "Please describe any pain you are having, including where it is, how severe it feels, what it feels like, and whether it spreads anywhere?",
        "past_evaluation": "Please describe any previous doctor visits, tests, or evaluations you have already had for this problem and what you were told?",
        "menstrual_pregnancy": "When was your last menstrual period, and have you noticed any cycle changes or a possibility of pregnancy?",
        "allergies": "Please describe any allergies to medicines, foods, or anything else that doctors should know about?",
        "closing": "Thank you, we have everything we need for now. Please arrive on time for your visit.",
    },
    "hi": {
        "reason_for_visit": "कृपया बताइए कि आज आपकी मुख्य स्वास्थ्य समस्या क्या है?",
        "onset_duration": "यह समस्या पहली बार कब शुरू हुई थी, और तब से लगातार है या बीच-बीच में होती है?",
        "severity_progression": "समय के साथ यह समस्या कैसे बदली है, जैसे बेहतर, बदतर, या लगभग वैसी ही?",
        "associated_symptoms": "इस समस्या के साथ आपने और कौन-कौन से लक्षण महसूस किए हैं?",
        "red_flag_check": "कृपया बताइए कि क्या कोई गंभीर चेतावनी वाले लक्षण हुए हैं, जैसे तेज दर्द, सांस की तकलीफ, बेहोशी, खून आना, या अचानक बिगड़ना?",
        "impact_daily_life": "यह समस्या आपकी रोजमर्रा की जिंदगी, जैसे नींद, खाना, काम, चलना-फिरना, या ऊर्जा पर कैसे असर डाल रही है?",
        "current_medications": "अभी आप इसके लिए कौन-कौन सी दवाएं, सप्लीमेंट, या घरेलू इलाज ले रहे हैं?",
        "past_medical_history": "कृपया अपनी पुरानी बीमारियों, सर्जरी, या बड़ी स्वास्थ्य समस्याओं के बारे में बताइए जो इससे जुड़ी हो सकती हैं?",
        "treatment_history": "अब तक आपने इस समस्या के लिए क्या इलाज या चिकित्सा सलाह ली है?",
        "recurrence_status": "कृपया बताइए कि यह नई समस्या है, पुरानी समस्या दोबारा हुई है, या किसी पुराने निदान का फॉलो-अप है?",
        "family_history": "क्या आपके परिवार में माता-पिता या भाई-बहनों को ऐसी या मिलती-जुलती स्वास्थ्य समस्या रही है?",
        "trigger_cause": "यह शुरू होने के आसपास क्या हुआ था, जैसे यात्रा, खाने में बदलाव, चोट, संक्रमण का संपर्क, या तनाव?",
        "travel_history": "कृपया अपनी हाल की किसी भी यात्रा के बारे में बताइए, जैसे आप कहाँ गए थे, कब गए थे, और क्या लक्षण यात्रा के दौरान या उसके बाद शुरू हुए?",
        "pain_assessment": "कृपया अपने दर्द के बारे में बताइए, जैसे कहाँ है, कितना तेज है, कैसा महसूस होता है, और क्या यह कहीं और फैलता है?",
        "past_evaluation": "कृपया बताइए कि इस समस्या के लिए आपने पहले कौन-कौन से डॉक्टर, जांच, या मूल्यांकन कराए हैं और आपको क्या बताया गया था?",
        "menstrual_pregnancy": "आपकी आखिरी माहवारी कब हुई थी, और क्या चक्र में कोई बदलाव या गर्भावस्था की संभावना है?",
        "allergies": "कृपया बताइए कि आपको दवाओं, खाने, या किसी और चीज से कोई एलर्जी है क्या?",
        "closing": "धन्यवाद, अभी के लिए हमें जरूरी जानकारी मिल गई है। कृपया समय पर आएं।",
    },
    "ta": {
        "reason_for_visit": "தயவுசெய்து இன்று நீங்கள் பேச விரும்பும் முக்கிய உடல்நல பிரச்சினை என்ன என்பதை சொல்லுங்கள்.",
        "onset_duration": "இந்த பிரச்சினை முதலில் எப்போது தொடங்கியது, அதன் பிறகு இது தொடர்ந்து இருந்ததா அல்லது இடையிடையே வந்ததா?",
        "severity_progression": "காலப்போக்கில் இந்த பிரச்சினை எப்படி மாறியது, உதாரணமாக மேம்பட்டதா, மோசமானதா, அல்லது கிட்டத்தட்ட அதேபோல இருந்ததா?",
        "associated_symptoms": "இந்த பிரச்சினையுடன் சேர்த்து நீங்கள் வேறு என்ன அறிகுறிகளை அனுபவித்துள்ளீர்கள்?",
        "red_flag_check": "கடுமையான வலி, மூச்சுத்திணறல், மயக்கம், இரத்தப்போக்கு, அல்லது திடீர் மோசமாதல் போன்ற எந்த தீவிர எச்சரிக்கை அறிகுறிகளும் இருந்ததா?",
        "impact_daily_life": "இந்த பிரச்சினை உங்கள் நாளாந்த வாழ்க்கையை, உதாரணமாக தூக்கம், உணவு, வேலை, நடமாட்டம், அல்லது சக்தியை எப்படி பாதிக்கிறது?",
        "current_medications": "இந்த பிரச்சினைக்காக நீங்கள் தற்போது எந்த மருந்துகள், சப்பிள்மென்ட்கள், அல்லது வீட்டு வைத்தியங்களை பயன்படுத்துகிறீர்கள்?",
        "past_medical_history": "இதற்கு தொடர்புடையதாக இருக்கக்கூடிய உங்கள் முந்தைய மருத்துவ நிலைகள், அறுவை சிகிச்சைகள், அல்லது பெரிய உடல்நல பிரச்சினைகள் பற்றி சொல்லுங்கள்.",
        "treatment_history": "இந்த பிரச்சினைக்காக இதுவரை நீங்கள் என்ன சிகிச்சை அல்லது மருத்துவ ஆலோசனை பெற்றுள்ளீர்கள்?",
        "recurrence_status": "இது புதிய பிரச்சினையா, பழைய பிரச்சினை மீண்டும் தோன்றியதா, அல்லது பழைய நோய்க்கான பின்தொடர்பா என்பதை சொல்லுங்கள்.",
        "family_history": "உங்கள் நெருங்கிய குடும்பத்தினரில், உதாரணமாக பெற்றோர் அல்லது உடன்பிறந்தோரில், இதுபோன்ற அல்லது தொடர்புடைய உடல்நல பிரச்சினைகள் இருந்ததா?",
        "trigger_cause": "இது தொடங்கிய நேரத்தில் அல்லது அதன் அருகில் ஏதேனும் நடந்ததா, உதாரணமாக பயணம், உணவு மாற்றம், காயம், தொற்று தொடர்பு, அல்லது மனஅழுத்தம்?",
        "travel_history": "நீங்கள் சமீபத்தில் செய்த பயணங்களை பற்றி சொல்லுங்கள், எங்கு சென்றீர்கள், எப்போது சென்றீர்கள், மற்றும் பயணத்தின் போது அல்லது பிறகு அறிகுறிகள் தொடங்கியதா?",
        "pain_assessment": "உங்களுக்கு இருக்கும் வலியை பற்றி சொல்லுங்கள், அது எங்கு உள்ளது, எவ்வளவு கடுமையாக உள்ளது, எப்படி உணரப்படுகிறது, மற்றும் வேறு இடங்களுக்கு பரவுகிறதா?",
        "past_evaluation": "இந்த பிரச்சினைக்காக நீங்கள் முன்பு கண்ட மருத்துவர் சந்திப்புகள், பரிசோதனைகள், அல்லது மதிப்பீடுகள் பற்றியும், உங்களிடம் என்ன கூறப்பட்டது என்பதையும் சொல்லுங்கள்.",
        "menstrual_pregnancy": "உங்கள் கடைசி மாதவிடாய் எப்போது வந்தது, மேலும் சுழற்சியில் ஏதேனும் மாற்றம் அல்லது கர்ப்பம் இருக்கக்கூடிய வாய்ப்பு உள்ளதா?",
        "allergies": "மருந்துகள், உணவு, அல்லது வேறு எதற்காவது உங்களுக்கு அலர்ஜி உள்ளதா? தயவுசெய்து சொல்லுங்கள்.",
        "closing": "நன்றி, தற்போது எங்களுக்கு தேவையான தகவல் கிடைத்துவிட்டது. தயவுசெய்து நேரத்திற்கு வாருங்கள்.",
    },
    "te": {
        "reason_for_visit": "దయచేసి ఈ రోజు మీరు చెప్పాలనుకునే ప్రధాన ఆరోగ్య సమస్య ఏమిటో వివరించండి.",
        "onset_duration": "ఈ సమస్య మొదట ఎప్పుడు ప్రారంభమైంది, అప్పటి నుంచి ఇది నిరంతరంగా ఉందా లేక మధ్య మధ్యలో వస్తోందా?",
        "severity_progression": "కాలక్రమంలో ఈ సమస్య ఎలా మారింది, అంటే మెరుగైందా, అధ్వాన్నమైందా, లేక దాదాపు అలాగే ఉందా?",
        "associated_symptoms": "ఈ సమస్యతో పాటు మీరు ఇంకేమేమి లక్షణాలు గమనించారు?",
        "red_flag_check": "తీవ్రమైన నొప్పి, శ్వాస తీసుకోవడంలో ఇబ్బంది, మూర్ఛ, రక్తస్రావం, లేదా అకస్మాత్తుగా అధ్వాన్నం కావడం వంటి ఏవైనా హెచ్చరిక లక్షణాలు ఉన్నాయా?",
        "impact_daily_life": "ఈ సమస్య మీ రోజువారీ జీవితం మీద ఎలా ప్రభావం చూపుతోంది, ఉదాహరణకు నిద్ర, భోజనం, పని, కదలిక, లేదా శక్తిపై?",
        "current_medications": "ఈ సమస్య కోసం మీరు ప్రస్తుతం ఏ మందులు, సప్లిమెంట్లు, లేదా ఇంటి చిట్కాలు ఉపయోగిస్తున్నారు?",
        "past_medical_history": "ఈ సమస్యకు సంబంధం ఉండవచ్చని భావించే మీ పూర్వ వైద్య సమస్యలు, శస్త్రచికిత్సలు, లేదా పెద్ద ఆరోగ్య సమస్యల గురించి చెప్పండి.",
        "treatment_history": "ఈ సమస్యకు ఇప్పటివరకు మీరు ఏ చికిత్స లేదా వైద్య సలహా తీసుకున్నారు?",
        "recurrence_status": "ఇది కొత్త సమస్యా, పాత సమస్య మళ్లీ వచ్చిందా, లేక పూర్వ నిర్ధారణకు ఫాలో-అప్‌నా?",
        "family_history": "మీ తల్లిదండ్రులు లేదా సహోదరుల్లో ఇలాంటి లేదా సంబంధిత ఆరోగ్య సమస్యలేమైనా ఉన్నాయా?",
        "trigger_cause": "ఇది ప్రారంభమైన సమయానికి దగ్గరగా ఏదైనా జరిగింది ఏమో, ఉదాహరణకు ప్రయాణం, ఆహార మార్పులు, గాయం, ఇన్ఫెక్షన్‌కి గురికావడం, లేదా ఒత్తిడి?",
        "travel_history": "మీరు ఇటీవల చేసిన ప్రయాణాల గురించి చెప్పండి, ఎక్కడికి వెళ్లారు, ఎప్పుడు వెళ్లారు, మరియు ప్రయాణ సమయంలో లేదా తర్వాత లక్షణాలు ప్రారంభమయ్యాయా?",
        "pain_assessment": "మీకు ఉన్న నొప్పి గురించి చెప్పండి, ఎక్కడ ఉంది, ఎంత తీవ్రముగా ఉంది, ఎలా అనిపిస్తోంది, మరియు అది ఇంకెక్కడికైనా వ్యాపిస్తున్నదా?",
        "past_evaluation": "ఈ సమస్య కోసం మీరు ఇంతకుముందు చేసిన డాక్టర్‌ సందర్శనలు, పరీక్షలు, లేదా మూల్యాంకనాల గురించి చెప్పండి, అలాగే మీకు ఏమని చెప్పారు?",
        "menstrual_pregnancy": "మీ చివరి మెన్స్ట్రుయల్‌ పీరియడ్‌ ఎప్పుడు వచ్చింది, అలాగే చక్రంలో ఏమైనా మార్పులు లేదా గర్భధారణకు అవకాశం ఉందా?",
        "allergies": "మందులు, ఆహారం, లేదా మరేదైనా వస్తువులకు మీకు అలర్జీలు ఉన్నాయా? దయచేసి చెప్పండి.",
        "closing": "ధన్యవాదాలు, ప్రస్తుతానికి మాకు అవసరమైన సమాచారం అందింది. దయచేసి సమయానికి రండి.",
    },
    "bn": {
        "reason_for_visit": "দয়া করে বলুন, আজ আপনি যে প্রধান স্বাস্থ্য সমস্যাটি নিয়ে কথা বলতে চান সেটি কী?",
        "onset_duration": "এই সমস্যা প্রথম কবে শুরু হয়েছিল, আর তারপর থেকে কি এটি সব সময় ছিল নাকি মাঝে মাঝে হয়েছে?",
        "severity_progression": "সময়ের সাথে এই সমস্যাটি কীভাবে বদলেছে, যেমন ভালো হয়েছে, খারাপ হয়েছে, নাকি প্রায় একই আছে?",
        "associated_symptoms": "এই সমস্যার সাথে আপনি আর কী কী উপসর্গ অনুভব করেছেন?",
        "red_flag_check": "তীব্র ব্যথা, শ্বাসকষ্ট, অজ্ঞান হওয়া, রক্তপাত, বা হঠাৎ খারাপ হয়ে যাওয়ার মতো কোনো গুরুতর সতর্ক সংকেত কি হয়েছে?",
        "impact_daily_life": "এই সমস্যা আপনার দৈনন্দিন জীবন, যেমন ঘুম, খাওয়া, কাজ, চলাফেরা, বা শক্তির ওপর কীভাবে প্রভাব ফেলছে?",
        "current_medications": "এই সমস্যার জন্য আপনি বর্তমানে কী কী ওষুধ, সাপ্লিমেন্ট, বা ঘরোয়া চিকিৎসা নিচ্ছেন?",
        "past_medical_history": "দয়া করে আপনার আগের রোগ, অস্ত্রোপচার, বা বড় স্বাস্থ্য সমস্যার কথা বলুন যেগুলো এর সাথে সম্পর্কিত হতে পারে।",
        "treatment_history": "এই সমস্যার জন্য এখন পর্যন্ত আপনি কী চিকিৎসা বা চিকিৎসকের পরামর্শ নিয়েছেন?",
        "recurrence_status": "দয়া করে বলুন এটি কি নতুন সমস্যা, পুরনো সমস্যার পুনরাবৃত্তি, নাকি পুরনো রোগের ফলো-আপ?",
        "family_history": "আপনার নিকট পরিবারে, যেমন বাবা-মা বা ভাইবোনদের মধ্যে, এ ধরনের বা সম্পর্কিত স্বাস্থ্য সমস্যা ছিল কি?",
        "trigger_cause": "এটি শুরু হওয়ার সময়ের কাছাকাছি কোনো কিছু ঘটেছিল কি, যেমন ভ্রমণ, খাবারে পরিবর্তন, আঘাত, সংক্রমণের সংস্পর্শ, বা মানসিক চাপ?",
        "travel_history": "আপনার সাম্প্রতিক ভ্রমণ সম্পর্কে বলুন, কোথায় গিয়েছিলেন, কবে গিয়েছিলেন, এবং ভ্রমণের সময় বা পরে উপসর্গ শুরু হয়েছিল কি না।",
        "pain_assessment": "আপনার ব্যথা সম্পর্কে বলুন, কোথায় হচ্ছে, কতটা তীব্র, কেমন লাগে, এবং অন্য কোথাও ছড়ায় কি না।",
        "past_evaluation": "এই সমস্যার জন্য আগের ডাক্তার দেখানো, পরীক্ষা, বা মূল্যায়নের কথা বলুন, এবং আপনাকে কী বলা হয়েছিল তাও জানান।",
        "menstrual_pregnancy": "আপনার শেষ মাসিক কবে হয়েছিল, আর চক্রে কোনো পরিবর্তন বা গর্ভধারণের সম্ভাবনা আছে কি?",
        "allergies": "ওষুধ, খাবার, বা অন্য কোনো কিছুর প্রতি আপনার কোনো অ্যালার্জি আছে কি? দয়া করে জানান।",
        "closing": "ধন্যবাদ, আপাতত আমাদের প্রয়োজনীয় তথ্য পাওয়া গেছে। অনুগ্রহ করে সময়মতো আসবেন।",
    },
    "mr": {
        "reason_for_visit": "कृपया सांगा, आज तुम्हाला कोणत्या मुख्य आरोग्य समस्येबद्दल बोलायचे आहे?",
        "onset_duration": "ही समस्या प्रथम कधी सुरू झाली, आणि तेव्हापासून सतत आहे का मधूनमधून होते?",
        "severity_progression": "काळानुसार ही समस्या कशी बदलली आहे, म्हणजे बरी झाली, वाढली, की जवळजवळ तशीच आहे?",
        "associated_symptoms": "या समस्येसोबत तुम्हाला अजून कोणती लक्षणे जाणवली आहेत?",
        "red_flag_check": "तीव्र वेदना, श्वास घेण्यास त्रास, बेशुद्ध पडणे, रक्तस्त्राव, किंवा अचानक प्रकृती बिघडणे अशी कोणती गंभीर लक्षणे झाली आहेत का?",
        "impact_daily_life": "ही समस्या तुमच्या रोजच्या आयुष्यावर, जसे झोप, खाणे, काम, हालचाल, किंवा उर्जा यावर कसा परिणाम करत आहे?",
        "current_medications": "या समस्येसाठी तुम्ही सध्या कोणती औषधे, सप्लिमेंट्स, किंवा घरगुती उपाय घेत आहात?",
        "past_medical_history": "या समस्येशी संबंधित असू शकतील अशा तुमच्या आधीच्या आजार, शस्त्रक्रिया, किंवा मोठ्या आरोग्य समस्यांबद्दल कृपया सांगा.",
        "treatment_history": "या समस्येसाठी आत्तापर्यंत तुम्ही कोणता उपचार किंवा वैद्यकीय सल्ला घेतला आहे?",
        "recurrence_status": "कृपया सांगा, ही नवीन समस्या आहे, जुन्या समस्येची पुनरावृत्ती आहे, की आधीच्या निदानाचा फॉलो-अप आहे?",
        "family_history": "तुमच्या जवळच्या कुटुंबात, जसे आई-वडील किंवा भावंडे, अशा किंवा यासारख्या आरोग्य समस्या झाल्या आहेत का?",
        "trigger_cause": "ही समस्या सुरू होण्याच्या सुमारास काही घडले होते का, जसे प्रवास, खाण्यात बदल, दुखापत, संसर्गाचा संपर्क, किंवा ताण?",
        "travel_history": "तुमच्या अलीकडील प्रवासाबद्दल सांगा, कुठे गेला होता, कधी गेला होता, आणि प्रवासादरम्यान किंवा नंतर लक्षणे सुरू झाली का?",
        "pain_assessment": "तुम्हाला होणाऱ्या वेदनांबद्दल सांगा, त्या कुठे आहेत, किती तीव्र आहेत, कशा वाटतात, आणि दुसरीकडे पसरतात का?",
        "past_evaluation": "या समस्येसाठी याआधी केलेल्या डॉक्टर भेटी, तपासण्या, किंवा मूल्यांकनांबद्दल सांगा, आणि तुम्हाला काय सांगितले गेले तेही सांगा.",
        "menstrual_pregnancy": "तुमची शेवटची मासिक पाळी कधी आली होती, आणि चक्रात काही बदल किंवा गर्भधारणेची शक्यता आहे का?",
        "allergies": "औषधे, अन्न, किंवा इतर कशामुळे तुम्हाला काही ॲलर्जी आहे का? कृपया सांगा.",
        "closing": "धन्यवाद, सध्या आम्हाला आवश्यक माहिती मिळाली आहे. कृपया वेळेवर या.",
    },
    "kn": {
        "reason_for_visit": "ದಯವಿಟ್ಟು ಇಂದು ನೀವು ಚರ್ಚಿಸಲು ಬಯಸುವ ಪ್ರಮುಖ ಆರೋಗ್ಯ ಸಮಸ್ಯೆ ಏನು ಎಂದು ತಿಳಿಸಿ.",
        "onset_duration": "ಈ ಸಮಸ್ಯೆ ಮೊದಲು ಯಾವಾಗ ಆರಂಭವಾಯಿತು, ಮತ್ತು ಆಗಿನಿಂದ ಇದು ನಿರಂತರವಾಗಿದೆಯೇ ಅಥವಾ ಮಧ್ಯೆ ಮಧ್ಯೆ ಆಗುತ್ತಿದೆಯೇ?",
        "severity_progression": "ಕಾಲಕ್ರಮದಲ್ಲಿ ಈ ಸಮಸ್ಯೆ ಹೇಗೆ ಬದಲಾಗಿದೆ, ಉದಾಹರಣೆಗೆ ಉತ್ತಮವಾಗಿದೆ, ಕೆಟ್ಟಿದೆ, ಅಥವಾ ಬಹುತೇಕ ಅದೇ ಇದೆ?",
        "associated_symptoms": "ಈ ಸಮಸ್ಯೆಯ ಜೊತೆಗೆ ನೀವು ಇನ್ನೇನು ಲಕ್ಷಣಗಳನ್ನು ಅನುಭವಿಸಿದ್ದೀರಿ?",
        "red_flag_check": "ತೀವ್ರ ನೋವು, ಉಸಿರಾಟದ ತೊಂದರೆ, ಮೂರ್ಛೆ, ರಕ್ತಸ್ರಾವ, ಅಥವಾ ಹಠಾತ್ ಹದಗೆಡುವಿಕೆ ಇತ್ಯಾದಿ ಗಂಭೀರ ಎಚ್ಚರಿಕೆ ಲಕ್ಷಣಗಳೇನಾದರೂ ಕಂಡಿದ್ದೀರಾ?",
        "impact_daily_life": "ಈ ಸಮಸ್ಯೆ ನಿಮ್ಮ ದಿನನಿತ್ಯದ ಬದುಕಿನ ಮೇಲೆ, ಉದಾಹರಣೆಗೆ ನಿದ್ರೆ, ಊಟ, ಕೆಲಸ, ಚಲನೆ, ಅಥವಾ ಶಕ್ತಿಯ ಮೇಲೆ ಹೇಗೆ ಪರಿಣಾಮ ಬೀರುತ್ತಿದೆ?",
        "current_medications": "ಈ ಸಮಸ್ಯೆಗೆ ನೀವು ಈಗ ಯಾವ ಔಷಧಿಗಳು, ಪೂರಕಗಳು, ಅಥವಾ ಮನೆಮದ್ದುಗಳನ್ನು ಬಳಸುತ್ತಿದ್ದೀರಿ?",
        "past_medical_history": "ಈ ಸಮಸ್ಯೆಗೆ ಸಂಬಂಧಿತವಾಗಿರಬಹುದಾದ ನಿಮ್ಮ ಹಿಂದಿನ ಕಾಯಿಲೆಗಳು, ಶಸ್ತ್ರಚಿಕಿತ್ಸೆಗಳು, ಅಥವಾ ದೊಡ್ಡ ಆರೋಗ್ಯ ಸಮಸ್ಯೆಗಳ ಬಗ್ಗೆ ದಯವಿಟ್ಟು ತಿಳಿಸಿ.",
        "treatment_history": "ಈ ಸಮಸ್ಯೆಗೆ ಇದುವರೆಗೆ ನೀವು ಯಾವ ಚಿಕಿತ್ಸೆ ಅಥವಾ ವೈದ್ಯಕೀಯ ಸಲಹೆ ಪಡೆದಿದ್ದೀರಿ?",
        "recurrence_status": "ದಯವಿಟ್ಟು ತಿಳಿಸಿ, ಇದು ಹೊಸ ಸಮಸ್ಯೆಯೇ, ಹಳೆಯ ಸಮಸ್ಯೆಯ ಮರುಕಳಿಕೆಯೇ, ಅಥವಾ ಹಿಂದಿನ ನಿರ್ಧಾರಿತ ಸಮಸ್ಯೆಯ ಫಾಲೋ-ಅಪ್‌ವೇ?",
        "family_history": "ನಿಮ್ಮ ಆಪ್ತ ಕುಟುಂಬದವರಾದ ತಂದೆ-ತಾಯಿ ಅಥವಾ ಸಹೋದರ-ಸಹೋದರಿಯರಲ್ಲಿ ಇಂತಹ ಅಥವಾ ಸಂಬಂಧಿತ ಆರೋಗ್ಯ ಸಮಸ್ಯೆಗಳಿದ್ದವೆಯೇ?",
        "trigger_cause": "ಇದು ಆರಂಭವಾದ ಸಮಯದ ಸುತ್ತಮುತ್ತ ಏನಾದರೂ ಸಂಭವಿಸಿತೇ, ಉದಾಹರಣೆಗೆ ಪ್ರಯಾಣ, ಆಹಾರದಲ್ಲಿ ಬದಲಾವಣೆ, ಗಾಯ, ಸೋಂಕಿನ ಸಂಪರ್ಕ, ಅಥವಾ ಒತ್ತಡ?",
        "travel_history": "ನಿಮ್ಮ ಇತ್ತೀಚಿನ ಪ್ರಯಾಣಗಳ ಬಗ್ಗೆ ತಿಳಿಸಿ, ಎಲ್ಲಿ ಹೋಗಿದ್ದೀರಿ, ಯಾವಾಗ ಪ್ರಯಾಣಿಸಿದ್ದೀರಿ, ಮತ್ತು ಲಕ್ಷಣಗಳು ಪ್ರಯಾಣದ ವೇಳೆ ಅಥವಾ ನಂತರ ಆರಂಭವಾಗಿದೆಯೇ?",
        "pain_assessment": "ನಿಮಗೆ ಇರುವ ನೋವಿನ ಬಗ್ಗೆ ತಿಳಿಸಿ, ಅದು ಎಲ್ಲಿ ಇದೆ, ಎಷ್ಟು ತೀವ್ರವಾಗಿದೆ, ಹೇಗೆ ಅನುಭವವಾಗುತ್ತದೆ, ಮತ್ತು ಬೇರೆಡೆಗೆ ಹರಡುತ್ತದೆಯೇ?",
        "past_evaluation": "ಈ ಸಮಸ್ಯೆಗೆ ಮೊದಲು ನಡೆದ ವೈದ್ಯರ ಭೇಟಿಗಳು, ಪರೀಕ್ಷೆಗಳು, ಅಥವಾ ಮೌಲ್ಯಮಾಪನಗಳ ಬಗ್ಗೆ ತಿಳಿಸಿ, ಮತ್ತು ನಿಮಗೆ ಏನು ಹೇಳಿದರು ಎಂಬುದನ್ನೂ ತಿಳಿಸಿ.",
        "menstrual_pregnancy": "ನಿಮ್ಮ ಕೊನೆಯ ಮಾಸಿಕ ಯಾವಾಗ ಆಯಿತು, ಮತ್ತು ಚಕ್ರದಲ್ಲಿ ಏನಾದರೂ ಬದಲಾವಣೆಗಳಿವೆಯೇ ಅಥವಾ ಗರ್ಭಧಾರಣೆಯ ಸಾಧ್ಯತೆ ಇದೆಯೇ?",
        "allergies": "ಔಷಧಿ, ಆಹಾರ, ಅಥವಾ ಬೇರೆ ಯಾವುದಕ್ಕೂ ನಿಮಗೆ ಅಲರ್ಜಿಗಳಿವೆಯೇ? ದಯವಿಟ್ಟು ತಿಳಿಸಿ.",
        "closing": "ಧನ್ಯವಾದಗಳು, ಸದ್ಯಕ್ಕೆ ನಮಗೆ ಅಗತ್ಯವಾದ ಮಾಹಿತಿ ದೊರಕಿದೆ. ದಯವಿಟ್ಟು ಸಮಯಕ್ಕೆ ಬನ್ನಿ.",
    },
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())

def normalize_topic_key(topic: str) -> str:
    normalized = _normalize_text(topic).replace(" ", "_")
    canonical = TOPIC_KEY_ALIASES.get(normalized, normalized)
    return canonical if canonical in ALLOWED_TOPICS else ""


def _normalize_topic_list(topics: list[str] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for topic in topics or []:
        canonical_topic = normalize_topic_key(topic)
        if canonical_topic and canonical_topic not in seen:
            seen.add(canonical_topic)
            normalized.append(canonical_topic)
    return normalized


def _normalize_question_text(value: str) -> str:
    text = _normalize_text(value)
    return re.sub(r"[^a-z0-9\u0900-\u097f\u0980-\u09ff\u0b80-\u0bff\u0c00-\u0c7f\u0c80-\u0cff\s]", "", text)


def _is_list_of_strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate_intake_message_quality(message: str, *, topic: str, language: str) -> dict:
    """Validate intake message quality in a reusable, side-effect-free way."""
    text = str(message or "").strip()
    if not text:
        return {"valid": False, "reason": "empty_message"}
    if len(text) > 180:
        return {"valid": False, "reason": "too_long"}

    normalized = _normalize_text(text)
    is_closing = normalize_topic_key(topic) == "closing"
    if not is_closing and not text.endswith("?"):
        return {"valid": False, "reason": "not_question_format"}

    low_value_prompts = {
        "yes or no?",
        "yes/no?",
        "yes?",
        "no?",
        "ok?",
        "okay?",
        "any issue?",
        "any problem?",
        "koi dikkat?",
        "haan ya na?",
        "haan/na?",
        "sirf haan ya na batayein?",
    }
    if normalized in low_value_prompts:
        return {"valid": False, "reason": "low_information_prompt"}
    if (normalized.startswith("yes or no") or normalized.startswith("haan ya na")) and len(normalized) <= 24:
        return {"valid": False, "reason": "low_information_prompt"}

    lang = normalize_intake_language(language)
    devanagari_chars = len(re.findall(r"[\u0900-\u097f]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))
    if lang == "hi":
        # Lightweight sanity: Hindi prompts should usually contain at least one Devanagari character.
        if devanagari_chars == 0:
            return {"valid": False, "reason": "language_mismatch"}
    elif lang == "hi-eng":
        # Hinglish should stay in Roman script and avoid Devanagari.
        if latin_chars == 0 or devanagari_chars > 0:
            return {"valid": False, "reason": "language_mismatch"}
    elif lang == "mr":
        if devanagari_chars == 0:
            return {"valid": False, "reason": "language_mismatch"}
    elif lang == "ta":
        if not re.search(r"[\u0b80-\u0bff]", text):
            return {"valid": False, "reason": "language_mismatch"}
    elif lang == "te":
        if not re.search(r"[\u0c00-\u0c7f]", text):
            return {"valid": False, "reason": "language_mismatch"}
    elif lang == "bn":
        if not re.search(r"[\u0980-\u09ff]", text):
            return {"valid": False, "reason": "language_mismatch"}
    elif lang == "kn":
        if not re.search(r"[\u0c80-\u0cff]", text):
            return {"valid": False, "reason": "language_mismatch"}
    elif lang == "en":
        # Lightweight sanity: English prompts should be mostly latin-script.
        if latin_chars == 0 or devanagari_chars > latin_chars:
            return {"valid": False, "reason": "language_mismatch"}

    return {"valid": True, "reason": ""}


class OpenAIQuestionClient:
    """Simple OpenAI wrapper for intake, summary, and vitals generation."""

    def generate_intake_turn(self, context: dict) -> dict:
        """Generate one intake turn from the dynamic intake template."""
        guidance = self._build_condition_guidance(context)
        template_path = Path(__file__).resolve().parent / "prompt_templates" / "intake_prompt.txt"
        template = template_path.read_text(encoding="utf-8")
        replacements = {
            "{{patient_name}}": str(context.get("patient_name", "") or ""),
            "{{patient_age}}": str(context.get("patient_age", "") or ""),
            "{{gender}}": str(context.get("gender", "") or ""),
            "{{language}}": normalize_intake_language(str(context.get("language", "en") or "en")),
            "{{question_number}}": str(int(context.get("question_number", 0) or 0)),
            "{{max_questions}}": str(int(context.get("max_questions", 8) or 8)),
            "{{previous_qa_json}}": json.dumps(context.get("previous_qa_json", []), ensure_ascii=True),
            "{{has_travelled_recently}}": "true" if bool(context.get("has_travelled_recently", False)) else "false",
            "{{chief_complaint}}": str(context.get("chief_complaint", "") or ""),
            "{{deterministic_condition_category}}": guidance["condition_category"],
            "{{deterministic_priority_topics}}": json.dumps(guidance["priority_topics"], ensure_ascii=True),
            "{{deterministic_avoid_topics}}": json.dumps(guidance["avoid_topics"], ensure_ascii=True),
        }
        prompt = template
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)

        try:
            content = self._chat_completion(
                prompt=prompt,
                system_role=(
                    "You are an expert clinical intake orchestration engine. "
                    "Follow the provided instructions exactly and return strict JSON only."
                ),
            )
        except (error.HTTPError, error.URLError, TimeoutError) as exc:
            raise IntakeTurnError("openai_http_error") from exc

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise IntakeTurnError("json_parse_error") from exc
        if not isinstance(result, dict):
            raise IntakeTurnError("schema_invalid")

        validation = self._validate_intake_turn_response(result)
        if not validation["valid"]:
            raise IntakeTurnError(
                self._map_validation_reason_to_fallback_reason(validation["reason_code"]),
                model_topic=normalize_topic_key(str(result.get("topic", "") or "")),
            )
        return self._enforce_condition_guidance(result=result, context=context, guidance=guidance)

    def detect_patient_opt_out(self, *, message_text: str, language: str, recent_answers: list[dict] | None = None) -> dict:
        """Detect whether the patient is asking to stop the intake flow."""
        template_path = Path(__file__).resolve().parent / "prompt_templates" / "opt_out_prompt.txt"
        template = template_path.read_text(encoding="utf-8")
        prompt = (
            template.replace("{{language}}", normalize_intake_language(str(language or "en"))).replace(
                "{{message_text}}", str(message_text or "")
            ).replace("{{recent_answers_json}}", json.dumps(recent_answers or [], ensure_ascii=True))
        )
        try:
            content = self._chat_completion(
                prompt=prompt,
                system_role=(
                    "You are a clinical intake stop-intent classifier. "
                    "Return strict JSON only with the required schema."
                ),
            )
        except (error.HTTPError, error.URLError, TimeoutError) as exc:
            raise RuntimeError("opt_out_detection_http_error") from exc

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("opt_out_detection_json_parse_error") from exc
        if not isinstance(result, dict):
            raise RuntimeError("opt_out_detection_schema_invalid")
        if not isinstance(result.get("is_opt_out"), bool):
            raise RuntimeError("opt_out_detection_schema_invalid")
        if not isinstance(result.get("confidence"), (int, float)):
            raise RuntimeError("opt_out_detection_schema_invalid")
        if not isinstance(result.get("reason"), str):
            raise RuntimeError("opt_out_detection_schema_invalid")

        result["confidence"] = float(result["confidence"])
        return result

    def generate_pre_visit_summary(self, language: str, intake_answers: list[dict]) -> dict:
        """Generate a structured five-section pre-visit summary."""
        template_path = Path(__file__).resolve().parent / "prompt_templates" / "summary_prompt.txt"
        template = template_path.read_text(encoding="utf-8")
        prompt = template.replace("{{language}}", language).replace(
            "{{intake_answers_json}}", json.dumps(intake_answers, ensure_ascii=True)
        )
        content = self._chat_completion(
            prompt=prompt,
            system_role="You generate structured pre-visit summaries for doctors.",
        )
        summary = json.loads(content)
        if not isinstance(summary, dict):
            raise RuntimeError("Model did not return object")
        return summary

    def generate_vitals_form(self, context: dict) -> dict:
        """Generate context-aware vitals requirement form."""
        template_path = Path(__file__).resolve().parent / "prompt_templates" / "vitals_prompt.txt"
        template = template_path.read_text(encoding="utf-8")
        prompt = template.replace("{{context_json}}", json.dumps(context, ensure_ascii=True))
        content = self._chat_completion(
            prompt=prompt,
            system_role=(
                "You decide if vitals are needed and output strict JSON only. "
                "Body weight and blood pressure are always collected by the system when vitals are needed. "
                "You choose zero to three additional fields only where intake/pre-visit justify them — do not pad to three. "
                "Contextual fields must be numeric clinical readings (field_type=number), not symptom narratives."
            ),
        )
        result = json.loads(content)
        if not isinstance(result, dict):
            raise RuntimeError("Model did not return object")
        return result

    def generate_india_clinical_note(self, context: dict) -> dict:
        """Generate India OPD clinical note from merged visit context."""
        template_path = Path(__file__).resolve().parent / "prompt_templates" / "india_note_prompt.txt"
        template = template_path.read_text(encoding="utf-8")
        prompt = template.replace("{{context_json}}", json.dumps(context, ensure_ascii=True))
        content = self._chat_completion(
            prompt=prompt,
            system_role=(
                "You generate strict JSON India OPD clinical notes. "
                "Follow schema exactly and do not output extra keys."
            ),
        )
        result = json.loads(content)
        if not isinstance(result, dict):
            raise RuntimeError("Model did not return object")
        return result

    def generate_post_visit_summary(self, *, context: dict, language_name: str) -> dict:
        """Generate patient-facing post-visit summary from structured context."""
        template_path = Path(__file__).resolve().parent / "prompt_templates" / "post_visit_summary_prompt.txt"
        template = template_path.read_text(encoding="utf-8")
        prompt = (
            template.replace("{{language_name}}", language_name).replace(
                "{{context_json}}", json.dumps(context, ensure_ascii=True)
            )
        )
        content = self._chat_completion(
            prompt=prompt,
            system_role=(
                "You generate strict JSON patient-facing post-visit summaries. "
                "Return only the required keys and no extra text."
            ),
        )
        result = json.loads(content)
        if not isinstance(result, dict):
            raise RuntimeError("Model did not return object")
        return result

    @staticmethod
    def _chat_completion(prompt: str, system_role: str) -> str:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        payload = {
            "model": settings.openai_model,
            "messages": [
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        req = request.Request(
            url="https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    @staticmethod
    def _validation_error(reason_code: str, field: str) -> dict:
        return {"valid": False, "reason_code": reason_code, "field": field}

    @staticmethod
    def _map_validation_reason_to_fallback_reason(reason_code: str) -> str:
        if reason_code == "missing_agent_block":
            return "agent_blocks_missing"
        if reason_code in MESSAGE_VALIDATION_REASON_CODES:
            return "message_invalid"
        return "schema_invalid"

    @classmethod
    def _normalize_topic_list_strict(cls, topics: list[str], field: str) -> dict:
        normalized: list[str] = []
        seen: set[str] = set()
        for topic in topics:
            canonical_topic = normalize_topic_key(topic)
            if not canonical_topic:
                return cls._validation_error("invalid_topic", field)
            if canonical_topic not in seen:
                seen.add(canonical_topic)
                normalized.append(canonical_topic)
        return {"valid": True, "reason_code": "", "field": field, "value": normalized}

    @classmethod
    def _validate_intake_turn_response(cls, result: dict) -> dict:
        required_top_level = ("agent1", "agent2", "agent4", "message", "topic", "is_complete")
        for key in required_top_level:
            if key not in result:
                reason = "missing_agent_block" if key in {"agent1", "agent2", "agent4"} else "missing_required_key"
                return cls._validation_error(reason, key)

        for agent_key in ("agent1", "agent2", "agent4"):
            if not isinstance(result.get(agent_key), dict):
                return cls._validation_error("missing_agent_block", agent_key)

        if not isinstance(result.get("message"), str):
            return cls._validation_error("invalid_type", "message")
        if not isinstance(result.get("is_complete"), bool):
            return cls._validation_error("invalid_type", "is_complete")
        if "question_number" in result and not isinstance(result.get("question_number"), int):
            return cls._validation_error("invalid_type", "question_number")

        agent1 = result["agent1"]
        agent2 = result["agent2"]
        agent4 = result["agent4"]

        for key in ("condition_category", "priority_topics"):
            if key not in agent1:
                return cls._validation_error("missing_required_key", f"agent1.{key}")
        for key in ("topics_covered", "information_gaps"):
            if key not in agent2:
                return cls._validation_error("missing_required_key", f"agent2.{key}")
        for key in ("next_topic", "stop_intake", "reason"):
            if key not in agent4:
                return cls._validation_error("missing_required_key", f"agent4.{key}")

        if not isinstance(agent1.get("condition_category"), str):
            return cls._validation_error("invalid_type", "agent1.condition_category")
        if not _is_list_of_strings(agent1.get("priority_topics")):
            return cls._validation_error("invalid_type", "agent1.priority_topics")
        if not _is_list_of_strings(agent2.get("topics_covered")):
            return cls._validation_error("invalid_type", "agent2.topics_covered")
        if not _is_list_of_strings(agent2.get("information_gaps")):
            return cls._validation_error("invalid_type", "agent2.information_gaps")
        if not isinstance(agent4.get("next_topic"), str):
            return cls._validation_error("invalid_type", "agent4.next_topic")
        if not isinstance(agent4.get("stop_intake"), bool):
            return cls._validation_error("invalid_type", "agent4.stop_intake")
        if not isinstance(agent4.get("reason"), str):
            return cls._validation_error("invalid_type", "agent4.reason")
        if not isinstance(result.get("topic"), str):
            return cls._validation_error("invalid_type", "topic")

        normalized_topic = normalize_topic_key(result["topic"])
        if not normalized_topic:
            return cls._validation_error("invalid_topic", "topic")
        result["topic"] = normalized_topic

        normalized_next_topic = normalize_topic_key(agent4["next_topic"])
        if not normalized_next_topic:
            return cls._validation_error("invalid_topic", "agent4.next_topic")
        agent4["next_topic"] = normalized_next_topic

        normalized_priority = cls._normalize_topic_list_strict(agent1["priority_topics"], "agent1.priority_topics")
        if not normalized_priority["valid"]:
            return normalized_priority
        agent1["priority_topics"] = normalized_priority["value"]

        normalized_covered = cls._normalize_topic_list_strict(agent2["topics_covered"], "agent2.topics_covered")
        if not normalized_covered["valid"]:
            return normalized_covered
        agent2["topics_covered"] = normalized_covered["value"]

        normalized_gaps = cls._normalize_topic_list_strict(agent2["information_gaps"], "agent2.information_gaps")
        if not normalized_gaps["valid"]:
            return normalized_gaps
        agent2["information_gaps"] = normalized_gaps["value"]

        return {"valid": True, "reason_code": "", "field": ""}

    @classmethod
    def _select_intake_message(
        cls,
        *,
        llm_message: str,
        llm_topic: str,
        enforced_topic: str,
        language: str,
        allow_llm_message: bool,
    ) -> dict:
        # Closing stays deterministic and backend-safe regardless of feature flags.
        if enforced_topic == "closing":
            return {
                "message": cls._topic_message("closing", language),
                "source": "template_fallback",
                "fallback_reason": "",
                "llm_message_valid": False,
            }
        if not str(llm_message or "").strip():
            return {
                "message": cls._topic_message(enforced_topic, language),
                "source": "template_fallback",
                "fallback_reason": "message_invalid",
                "llm_message_valid": False,
            }
        if normalize_topic_key(llm_topic) != enforced_topic:
            return {
                "message": cls._topic_message(enforced_topic, language),
                "source": "template_fallback",
                "fallback_reason": "topic_mismatch",
                "llm_message_valid": False,
            }
        message_validation = validate_intake_message_quality(llm_message, topic=enforced_topic, language=language)
        # Normal intake questions should stay model-generated; template fallback is reserved
        # for closing/safety or actual model failure before this selector is reached.
        return {
            "message": llm_message,
            "source": "llm",
            "fallback_reason": "",
            "llm_message_valid": bool(message_validation["valid"]),
        }

    @classmethod
    def _build_condition_guidance(cls, context: dict) -> dict:
        complaint = _normalize_text(context.get("chief_complaint", ""))
        category = cls._infer_condition_category(complaint)
        priority_topics = cls._build_universal_topic_plan(context=context, complaint=complaint)
        avoid_topics: list[str] = []

        gender = _normalize_text(context.get("gender", ""))
        age = context.get("patient_age")
        try:
            age_value = int(age) if age not in ("", None) else None
        except (TypeError, ValueError):
            age_value = None

        if "menstrual_pregnancy" in priority_topics and category != "womens_health_related":
            priority_topics = [topic for topic in priority_topics if topic != "menstrual_pregnancy"]
        if gender in {"male", "m", "man", "boy"} or (age_value is not None and age_value < 12):
            if "menstrual_pregnancy" in priority_topics:
                priority_topics = [topic for topic in priority_topics if topic != "menstrual_pregnancy"]
            if "menstrual_pregnancy" not in avoid_topics:
                avoid_topics.append("menstrual_pregnancy")

        return {
            "condition_category": category,
            "priority_topics": _normalize_topic_list(priority_topics),
            "avoid_topics": _normalize_topic_list(avoid_topics),
        }

    @classmethod
    def _infer_condition_category(cls, complaint: str) -> str:
        if not complaint or complaint in {"hi", "hello", "hey", "ok", "okay", "yes", "no"}:
            return "general_other"
        if any(keyword in complaint for keyword in WOMENS_HEALTH_KEYWORDS):
            return "womens_health_related"
        if any(keyword in complaint for keyword in ALLERGY_KEYWORDS):
            return "allergy_related"
        if any(keyword in complaint for keyword in PAIN_KEYWORDS):
            return "pain_related"
        if any(keyword in complaint for keyword in CHRONIC_KEYWORDS | HEREDITARY_KEYWORDS):
            return "chronic_or_hereditary"
        return "general_other"

    @classmethod
    def _build_universal_topic_plan(cls, context: dict, complaint: str) -> list[str]:
        has_travel = bool(context.get("has_travelled_recently", False))
        is_chronic = any(keyword in complaint for keyword in CHRONIC_KEYWORDS)
        is_hereditary = any(keyword in complaint for keyword in HEREDITARY_KEYWORDS)
        is_allergy = any(keyword in complaint for keyword in ALLERGY_KEYWORDS)
        is_pain = any(keyword in complaint for keyword in PAIN_KEYWORDS)
        is_womens = any(keyword in complaint for keyword in WOMENS_HEALTH_KEYWORDS)

        base_topics = [
            # Always start with the patient's reason for visit, even if a short chief complaint
            # was already collected as "illness" in history. This keeps the first LLM turn
            # patient-facing and consistent across channels.
            "reason_for_visit",
            "onset_duration",
            "associated_symptoms",
            "current_medications",
            "past_medical_history",
            "trigger_cause",
            ("travel_history" if has_travel else "impact_daily_life"),
        ]

        if is_chronic or is_hereditary:
            branch_topic = "family_history"
        elif is_allergy:
            branch_topic = "allergies"
        elif is_pain:
            branch_topic = "pain_assessment"
        else:
            branch_topic = "severity_progression"

        final_branch_topic = "menstrual_pregnancy" if is_womens else "past_evaluation"
        return base_topics + [branch_topic, final_branch_topic]

    @classmethod
    def _extract_covered_topics(cls, context: dict) -> list[str]:
        covered: list[str] = []
        for qa in context.get("previous_qa_json", []) or []:
            topic = cls._infer_topic_from_qa(qa)
            if topic and topic not in covered:
                covered.append(topic)
        return covered

    @classmethod
    def _infer_topic_from_qa(cls, qa: dict | None) -> str:
        item = qa or {}
        explicit_topic = normalize_topic_key(str(item.get("topic", "") or ""))
        if explicit_topic:
            return explicit_topic

        question = str(item.get("question", "") or "")
        normalized_question = _normalize_question_text(question)
        if normalized_question == "illness":
            # Intake service stores the initial chief complaint as question="illness".
            # Treat it as reason_for_visit coverage to prevent repeating the same ask.
            return "reason_for_visit"
        if not normalized_question:
            return ""

        for language_topics in TOPIC_QUESTION_TEMPLATES.values():
            for topic, template in language_topics.items():
                if topic == "closing":
                    continue
                if _normalize_question_text(template) == normalized_question:
                    return normalize_topic_key(topic)

        keyword_map = {
            "reason_for_visit": ["main health issue", "health problem", "concern brings you", "मुख्य स्वास्थ्य समस्या"],
            "onset_duration": ["when did this problem first start", "पहली बार कब शुरू"],
            "severity_progression": ["changing over time", "better worse", "समय के साथ"],
            "associated_symptoms": ["other symptoms", "और कौन", "लक्षण"],
            "red_flag_check": ["warning signs", "गंभीर चेतावनी", "severe pain", "breathlessness"],
            "impact_daily_life": ["daily routine", "रोजमर्रा", "sleep eating work"],
            "current_medications": ["medicines supplements", "दवाएं", "home remedies"],
            "past_medical_history": ["past medical conditions", "पुरानी बीमारियों", "surgeries"],
            "treatment_history": ["treatment or medical care", "क्या इलाज", "medical care"],
            "recurrence_status": ["new problem", "recurrence", "फॉलोअप", "फॉलो-अप"],
            "family_history": ["close family", "परिवार", "parents or siblings"],
            "trigger_cause": ["around the time this started", "शुरू होने के आसपास", "travel food changes injury"],
            "travel_history": ["recent travel", "हाल की किसी भी यात्रा", "during or after the trip"],
            "pain_assessment": ["pain you are having", "दर्द", "how severe it feels"],
            "past_evaluation": ["previous doctor visits", "पहले कौनकौन से डॉक्टर", "what you were told"],
            "menstrual_pregnancy": ["last menstrual period", "आखिरी माहवारी", "possibility of pregnancy"],
            "allergies": ["allergies to medicines", "एलर्जी", "foods or anything else"],
        }
        for topic, phrases in keyword_map.items():
            if any(phrase in normalized_question for phrase in phrases):
                return normalize_topic_key(topic)
        return ""

    @classmethod
    def _next_topic_from_plan(cls, context: dict, guidance: dict) -> str:
        covered = set(cls._extract_covered_topics(context))
        avoid = set(guidance["avoid_topics"])
        # Backward-compat: if the flow has already progressed (e.g., onset_duration collected)
        # but older sessions never asked reason_for_visit, do not "go backwards".
        # Only ask reason_for_visit as the first LLM turn when no other clinical topics
        # have been covered yet.
        if "reason_for_visit" not in covered:
            progressed_topics = {t for t in covered if t not in {"reason_for_visit", "closing"}}
            if progressed_topics:
                covered.add("reason_for_visit")
        for topic in guidance["priority_topics"]:
            if topic not in covered and topic not in avoid:
                return topic
        return "closing"

    @classmethod
    def _topic_message(cls, topic: str, language: str) -> str:
        lang = normalize_intake_language(language)
        templates = TOPIC_QUESTION_TEMPLATES.get(lang) or TOPIC_QUESTION_TEMPLATES["en"]
        return templates.get(topic) or templates["reason_for_visit"]

    @classmethod
    def _enforce_condition_guidance(cls, result: dict, context: dict, guidance: dict) -> dict:
        settings = get_settings()
        allow_llm_message = settings.intake_use_llm_message
        language = normalize_intake_language(str(context.get("language", "en") or "en"))
        agent1 = result.get("agent1") if isinstance(result.get("agent1"), dict) else {}
        agent2 = result.get("agent2") if isinstance(result.get("agent2"), dict) else {}
        agent4 = result.get("agent4") if isinstance(result.get("agent4"), dict) else {}
        llm_topic = normalize_topic_key(str(result.get("topic", "") or ""))
        llm_message = str(result.get("message", "") or "").strip()

        enforced_next_topic = cls._next_topic_from_plan(context=context, guidance=guidance)
        if result.get("is_complete"):
            enforced_next_topic = "closing"

        agent1["condition_category"] = guidance["condition_category"]
        agent1["priority_topics"] = guidance["priority_topics"]
        existing_avoid = _normalize_topic_list(agent1.get("avoid_topics"))
        merged_avoid = _normalize_topic_list(existing_avoid + guidance["avoid_topics"])
        agent1["avoid_topics"] = merged_avoid
        agent1["topic_plan"] = guidance["priority_topics"]

        covered = _normalize_topic_list(agent2.get("topics_covered") or [])
        covered = _normalize_topic_list(covered + cls._extract_covered_topics(context))
        agent2["topics_covered"] = covered
        agent2["information_gaps"] = [
            topic for topic in guidance["priority_topics"] if topic not in covered and topic not in merged_avoid
        ]
        agent2["redundant_categories"] = _normalize_topic_list(agent2.get("redundant_categories"))

        is_complete = enforced_next_topic == "closing"
        agent4["next_topic"] = enforced_next_topic
        agent4["stop_intake"] = is_complete
        agent4["reason"] = (
            f"Using deterministic topic plan for {guidance['condition_category']}."
            if not is_complete
            else "No remaining required topics for this illness category."
        )

        result["agent1"] = agent1
        result["agent2"] = agent2
        result["agent4"] = agent4
        result["fields_collected"] = covered
        result["fields_missing"] = agent2["information_gaps"]
        result["topic"] = enforced_next_topic
        result["is_complete"] = is_complete
        if not isinstance(result.get("question_number"), int):
            result["question_number"] = int(context.get("question_number", 1) or 1)
        message_selection = cls._select_intake_message(
            llm_message=llm_message,
            llm_topic=llm_topic,
            enforced_topic=enforced_next_topic,
            language=language,
            allow_llm_message=allow_llm_message,
        )
        result["message"] = message_selection["message"]
        result["last_message_source"] = message_selection["source"]
        result["last_fallback_reason"] = message_selection["fallback_reason"]
        result["last_selected_topic"] = enforced_next_topic
        result["last_model_topic"] = llm_topic
        result["llm_structure_valid"] = True
        result["llm_message_valid"] = bool(message_selection["llm_message_valid"])

        return result
