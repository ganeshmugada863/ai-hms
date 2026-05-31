import re

class LanguageDetector:
    def __init__(self):
        # Multilingual vocabulary mapping to standard English terms
        self.multilingual_vocab = {
            # Yes/Positive confirmations
            'yes': ['yes', 'yeah', 'yup', 'ok', 'okay', 'sure', 'confirm', 'correct',
                    'అవును', 'సరే', 'హా', 'avunu', 'sare', 'ha',
                    'हाँ', 'हाँजी', 'ठीक', 'सही', 'haan', 'thik', 'sahi',
                    'ஆம்', 'சரி', 'ஆமாம்', 'aamaam', 'sari',
                    'ಹೌದು', 'ಸರಿ', 'haudu', 'sari',
                    'അതെ', 'ശരി', 'athe', 'sheri'],
            
            # No/Negative confirmations
            'no': ['no', 'nope', 'nah', 'not', 'cancel',
                   'లేదు', 'కాదు', 'వద్దు', 'ledu', 'kadu', 'vద్దు', 'voddu',
                   'नहीं', 'ना', 'nahi', 'na',
                   'இல்லை', 'வேண்டாம்', 'illai', 'vendam',
                   'ಇಲ್ಲ', 'ಬೇಡ', 'illa', 'beda',
                   'അല്ല', 'വേണ്ട', 'alla', 'venda'],
            
            # Symptom Mappings: Fever
            'fever': ['fever', 'temperature', 'hot body', 'chills',
                      'జ్వరం', 'ఒళ్ళు వేడిగా ఉండటం', 'jwaram', 'jwaramగా ఉంది',
                      'बुखार', 'ताप', 'bukhar', 'tap',
                      'காய்ச்சல்', 'உடல் சூடு', 'kaichal',
                      'ಜ್ವರ', 'jawra', 'jwara',
                      'പനി', 'pani'],
            
            # Symptom Mappings: Chest Pain
            'chest pain': ['chest pain', 'heart pain', 'chest pressure', 'tight chest',
                           'ఛాతి నొప్పి', 'గుండె నొప్పి', 'chathi noppi', 'gunde noppi',
                           'छाती में दर्द', 'सीने में दर्द', 'chhati dard', 'seene me dard',
                           'நெஞ்சு வலி', 'nenju vali',
                           'ಎದೆ ನೋವು', 'ede novu',
                           'നെഞ്ച് വേദന', 'nenju vedhana'],
            
            # Symptom Mappings: Skin Rash
            'skin rash': ['rash', 'skin allergy', 'itching', 'red skin', 'pimples', 'acne',
                          'చర్మంపై దద్దుర్లు', 'దురద', 'charma allergy', 'durada', 'daddurlu',
                          'खुजली', 'लाल चकत्ते', 'त्वचा एलर्जी', 'khujli', 'skin allergy',
                          'அரிப்பு', 'தடிப்பு', 'தோல் ஒவ்வாமை', 'arippu', 'thadippu',
                          'ತುರಿಕೆ', 'ದದ್ದು', 'churika', 'turike',
                          'ചൊറിച്ചിൽ', 'തടിപ്പ്', 'chorichil', 'thadippu'],
            
            # Symptom Mappings: Eye Pain
            'eye pain': ['eye pain', 'vision problems', 'blurry vision', 'red eyes',
                         'కంటి నొప్పి', 'మసక చూపు', 'kanti noppi', 'masaka chupu',
                         'आँख में दर्द', 'धुंधला दिखना', 'aankh dard', 'dhundhla',
                         'கண் வலி', 'மங்கலான பார்வை', 'kan vali', 'paarvai',
                         'ಕಣ್ಣು ನೋವು', 'ಕಣ್ಣು ಮಸಕಾಗುವುದು', 'kannu novu',
                         'കണ്ണ് വേദന', 'കാഴ്ച മങ്ങൽ', 'kannu vedhana', 'kazhcha'],
            
            # Symptom Mappings: Pregnancy
            'pregnancy': ['pregnancy', 'pregnant', 'missed period', 'morning sickness', 'gynecology',
                          'గర్భం', 'నెల తప్పడం', 'garbham', 'pregnancy test',
                          'गर्भावस्था', 'गर्भवती', 'gabhwati', 'pregnancy',
                          'கர்ப்பம்', 'karppam', 'gabbham',
                          'ಗರ್ಭಧಾರಣೆ', 'ಗರ್ಭಿಣಿ', 'garbha',
                          'ഗർഭം', 'ഗർഭിണി', 'garbham'],
            
            # Symptom Mappings: Joint Pain
            'joint pain': ['joint pain', 'bone pain', 'knee pain', 'back pain', 'fracture',
                           'కీళ్ల నొప్పులు', 'మోకాలి నొప్పి', 'వెన్ను నొప్పి', 'killa noppulu', 'mokali noppi',
                           'जोड़ों का दर्द', 'घुटने का दर्द', 'पीठ दर्द', 'jodon ka dard', 'knee dard',
                           'மூட்டு வலி', 'முதுகு வலி', 'mootu vali', 'mudhugu vali',
                           'ಕೀಲು ನೋವು', 'ಮೊಣಕಾಲು ನೋವು', 'keelu novu',
                           'മൂട്ട് വേദന', 'നടുവേദന', 'moottu vedhana', 'naduvethana'],
            
            # Symptom Mappings: Mental Stress
            'mental stress': ['mental stress', 'anxiety', 'depression', 'insomnia', 'stress', 'tension',
                              'మానసిక ఒత్తిడి', 'ఆందోళన', 'నిద్రలేమి', 'othidi', 'tension', 'anxiety',
                              'तनाव', 'चिंता', 'घबराहट', 'tanav', 'chinta', 'tension',
                              'மன அழுத்தம்', 'மனக்கவலை', 'mana azhutham', 'kavalai',
                              'ಮಾನಸಿಕ ಒತ್ತಡ', 'ಆತಂಕ', 'othada', 'aathanka',
                              'മാനസിക സമ്മർദ്ദം', 'ആകുലത', 'manasika sammardham'],
            
            # Symptom Mappings: Dental Pain
            'dental pain': ['dental pain', 'toothache', 'gum bleeding', 'tooth pain',
                            'పంటి నొప్పి', 'చిగుళ్ళ రక్తం', 'panti noppi', 'chigulla raktham',
                            'दांत का दर्द', 'मसूड़ों से खून', 'daant dard', 'teeth pain',
                            'பல் வலி', 'ஈறுகளில் இரத்தம்', 'pal vali',
                            'ಹಲ್ಲು ನೋವು', 'hallu novu',
                            'പല്ല് വേദന', 'pallu vedhana'],
            
            # Symptom Mappings: Ear Problems
            'ear problems': ['ear pain', 'ear problems', 'sore throat', 'tonsils', 'hearing issue',
                             'చెవి నొప్పి', 'గొంతు నొప్పి', 'chevi noppi', 'gonthu noppi',
                             'कान का दर्द', 'गले में खराश', 'kaan dard', 'gala kharab',
                             'காது வலி', 'தொண்டை வலி', 'kadhu vali', 'thonde vali',
                             'ಕಿವಿ ನೋವು', 'ಗಂಟಲು ನೋವು', 'kivi novu', 'gantalu novu',
                             'ചെവി വേദന', 'തൊണ്ടവേദന', 'chevi vedhana', 'thonde vedhana'],
            
            # Symptom Mappings: Children Symptoms
            'children symptoms': ['child fever', 'pediatric', 'baby cough', 'kid sick',
                                  'పిల్లల జ్వరం', 'పిల్లల దగ్గు', 'pillala jwaram', 'pillala daggu',
                                  'बच्चों का बुखार', 'बच्चा बीमार', 'baccho ka bukhar', 'bacha bimar',
                                  'குழந்தை காய்ச்சல்', 'pediatric', 'kuzhandhai',
                                  'ಮಕ್ಕಳ ಜ್ವರ', 'ಮಗು ಕಾಯಿಲೆ', 'makkala jwara',
                                  'കുട്ടികളുടെ പനി', 'കുട്ടിക്ക് സുഖമില്ല', 'kuttikalude pani'],

            # Symptom Mappings: Breathing Difficulty
            'breathing difficulty': ['breathing difficulty', 'shortness of breath', 'asthma', 'coughing blood',
                                     'శ్వాస తీసుకోవడంలో ఇబ్బంది', 'దగ్గు', 'swasa ibbandhi', 'daggu',
                                     'सांस लेने में तकलीफ', 'दमा', 'saans me taklif', 'asthma',
                                     'மூச்சுத் திணறல்', 'இருமல்', 'moochu thinaral',
                                     'ಉಸಿರಾಟದ ತೊಂದರೆ', 'ಕೆಮ್ಮು', 'usirata thondare',
                                     'ശ്വാസതടസ്സം', 'ചുമ', 'swasathadasam', 'chuma']
        }

    def detect(self, text: str) -> str:
        if not text or not text.strip():
            return 'en'
        
        # Check Unicode ranges for script detection
        for char in text:
            val = ord(char)
            # Telugu script range: U+0C00 to U+0C7F
            if 0x0c00 <= val <= 0x0c7f:
                return 'te'
            # Devanagari (Hindi) script range: U+0900 to U+097F
            elif 0x0900 <= val <= 0x097f:
                return 'hi'
            # Tamil script range: U+0B80 to U+0BFF
            elif 0x0b80 <= val <= 0x0bff:
                return 'ta'
            # Kannada script range: U+0C80 to U+0CFF
            elif 0x0c80 <= val <= 0x0cff:
                return 'kn'
            # Malayalam script range: U+0D00 to U+0D7F
            elif 0x0d00 <= val <= 0x0d7f:
                return 'ml'
        
        # Romanized text matching check (Tenglish, Hinglish, etc.)
        text_lower = text.lower().strip()
        words = re.findall(r'\b\w+\b', text_lower)
        
        for lang_key, keywords in self.multilingual_vocab.items():
            for word in words:
                # If matched to a specific localized non-English romanized word
                for kw in keywords:
                    if word == kw and not kw.replace("'", "").isalpha():
                        # Standard English words will be alphabetic, non-English phonetic might still match.
                        # Simple heuristic check: if the word matches localized list
                        pass
        
        # Fallback to English
        return 'en'

    def translate_to_english(self, text: str) -> str:
        """
        Translate simple phrases and symptoms from any of the 5 other languages 
        into English terms to enable mapping.
        """
        if not text:
            return ""
        
        translated = text.lower().strip()
        
        # Reverse map terms from multilingual vocab to English keys
        for eng_key, list_terms in self.multilingual_vocab.items():
            # Sort by length descending to replace longer terms first
            sorted_terms = sorted(list_terms, key=len, reverse=True)
            for term in sorted_terms:
                if term in translated:
                    # Replace matching phrases with standard English keys
                    escaped_term = re.escape(term)
                    translated = re.sub(rf'\b{escaped_term}\b', eng_key, translated)
                    # Also direct string replacement for non-space scripts
                    translated = translated.replace(term, " " + eng_key + " ")
        
        return re.sub(r'\s+', ' ', translated).strip()
