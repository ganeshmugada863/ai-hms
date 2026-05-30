import os
import csv
import re
from langdetect import detect as ld_detect, DetectorFactory

# Set seed for langdetect to be deterministic
DetectorFactory.seed = 0

class LanguageDetector:
    def __init__(self, dataset_dir=None):
        self.te_to_en = {}
        self.en_to_te = {}
        self.tenglish_to_en = {}
        
        # Default fallback dictionary in case CSV loading fails
        self.fallback_te_to_en = {
            "తలనొప్పి": "headache",
            "జ్వరం": "fever",
            "దగ్గు": "cough",
            "జలుబు": "cold",
            "వాంతులు": "vomiting",
            "కడుపు నొప్పి": "stomach pain",
            "నొప్పి": "pain",
            "tala noppi": "headache",
            "jwaram": "fever",
            "daggu": "cough",
            "kadupu noppi": "stomach pain",
            "noppi": "pain",
            "jalubu": "cold",
        }
        self.fallback_en_to_te = {
            "headache": "తలనొప్పి",
            "fever": "జ్వరం",
            "cough": "దగ్గు",
            "cold": "జలుబు",
            "vomiting": "వాంతులు",
            "stomach pain": "కడుపు నొప్పి",
            "pain": "నొప్పి",
        }
        
        # Load from telugu.csv if path is provided or can be found
        if not dataset_dir:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dataset_dir = os.path.join(current_dir, 'datasets')
            
        csv_path = os.path.join(dataset_dir, 'telugu.csv')
        if os.path.exists(csv_path):
            try:
                with open(csv_path, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        en = row.get('english', '').strip().lower()
                        te = row.get('telugu', '').strip().lower()
                        ten = row.get('tenglish', '').strip().lower()
                        if en:
                            if te:
                                self.te_to_en[te] = en
                                self.en_to_te[en] = te
                            if ten:
                                self.tenglish_to_en[ten] = en
            except Exception as e:
                print(f"Warning: Failed to load telugu.csv: {e}")
                
        # Merge with fallback mappings if not already present
        for k, v in self.fallback_te_to_en.items():
            if "త" in k or "జ" in k or "ద" in k or "వ" in k or "క" in k or "న" in k:  # Telugu script characters
                if k not in self.te_to_en:
                    self.te_to_en[k] = v
            else:  # Tenglish characters
                if k not in self.tenglish_to_en:
                    self.tenglish_to_en[k] = v
        for k, v in self.fallback_en_to_te.items():
            if k not in self.en_to_te:
                self.en_to_te[k] = v

    def is_telugu_script(self, text: str) -> bool:
        # Unicode range for Telugu is U+0C00 to U+0C7F
        for char in text:
            if '\u0c00' <= char <= '\u0c7f':
                return True
        return False

    def detect(self, text: str) -> str:
        if not text or not text.strip():
            return 'en'
            
        # Check for Telugu script characters first (highest confidence indicator)
        if self.is_telugu_script(text):
            return 'te'
            
        # Check for common Romanized Telugu words (Tenglish)
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        for word in words:
            if word in self.tenglish_to_en:
                return 'te'
                
        # Fall back to the langdetect library
        try:
            lang = ld_detect(text)
            if lang == 'te':
                return 'te'
        except Exception:
            pass
            
        return 'en'

    def translate_to_english(self, text: str) -> str:
        if not text:
            return ""
            
        translated = text.lower()
        
        # 1. Translate Telugu script terms to English
        te_sorted = sorted(self.te_to_en.keys(), key=len, reverse=True)
        for te_phrase in te_sorted:
            if te_phrase in translated:
                translated = translated.replace(te_phrase, self.te_to_en[te_phrase])
                
        # 2. Translate Romanized Telugu (Tenglish) terms to English
        ten_sorted = sorted(self.tenglish_to_en.keys(), key=len, reverse=True)
        for ten_phrase in ten_sorted:
            escaped_phrase = re.escape(ten_phrase)
            # Match whole phrase or word to prevent partial replacements (e.g. "noppi" in "noppiga")
            translated = re.sub(rf'\b{escaped_phrase}\b', self.tenglish_to_en[ten_phrase], translated)
            
        return translated

    def translate_to_telugu(self, text: str) -> str:
        if not text:
            return ""
            
        translated = text.lower()
        
        # Translate English terms to Telugu script equivalents
        en_sorted = sorted(self.en_to_te.keys(), key=len, reverse=True)
        for en_phrase in en_sorted:
            escaped_phrase = re.escape(en_phrase)
            translated = re.sub(rf'\b{escaped_phrase}\b', self.en_to_te[en_phrase], translated)
            
        return translated
