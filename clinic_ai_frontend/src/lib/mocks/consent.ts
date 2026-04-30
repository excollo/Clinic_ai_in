import apiClient from "@/lib/apiClient";

export async function fetchConsentText(language: string) {
  try {
    const response = await apiClient.get("/consent/text", { params: { language, version: "latest" } });
    return String(response.data?.text ?? "");
  } catch {
    await new Promise((resolve) => setTimeout(resolve, 300));
    if (language.toLowerCase().includes("hindi")) {
      return `मैं सहमति देता/देती हूं कि डॉक्टर मेरी स्वास्थ्य जानकारी, लक्षण, और परामर्श से संबंधित विवरण दर्ज कर सकते हैं।\n\nमैं सहमति देता/देती हूं कि परामर्श की ऑडियो रिकॉर्डिंग की जा सकती है ताकि उपचार की गुणवत्ता बेहतर हो।\n\nमैं सहमति देता/देती हूं कि प्रिस्क्रिप्शन, फॉलो-अप और रिमाइंडर WhatsApp पर भेजे जा सकते हैं।\n\nमैं सहमति देता/देती हूं कि लैब रिपोर्ट्स को मेरी विज़िट से जोड़ा जा सकता है।\n\nमेरा डेटा केवल डॉक्टर/क्लिनिक के उपयोग के लिए रहेगा और मेरी अनुमति के बिना साझा नहीं किया जाएगा।\n\nमैं कभी भी अपनी सहमति वापस ले सकता/सकती हूं।`;
    }
    return `I consent to recording of my symptoms and clinical information for treatment.\n\nI consent to consultation audio recording for documentation quality.\n\nI consent to receiving prescriptions and reminders over WhatsApp.\n\nI consent to linking lab reports with my visits.\n\nMy data remains with my doctor/clinic and is not shared without authorization.\n\nI can withdraw consent at any time.`;
  }
}
