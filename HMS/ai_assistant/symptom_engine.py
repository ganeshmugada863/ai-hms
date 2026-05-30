import os
import csv
import re
import numpy as np

try:
    from sentence_transformers import SentenceTransformer, util
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

class SymptomEngine:
    def __init__(self, dataset_dir=None):
        self.symptoms = []  # List of dicts from symptoms.csv
        self.english_mappings = []  # List of dicts from english.csv
        self.diseases = []  # List of dicts from diseases.csv
        self.model = None
        self.symptom_embeddings = None
        self.mapping_embeddings = None
        
        if not dataset_dir:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dataset_dir = os.path.join(current_dir, 'datasets')
            
        self.dataset_dir = dataset_dir
        self._load_datasets()
        
        if HAS_TRANSFORMERS:
            self._init_model()
            
    def _load_datasets(self):
        # Load symptoms
        symptoms_path = os.path.join(self.dataset_dir, 'symptoms.csv')
        if os.path.exists(symptoms_path):
            try:
                with open(symptoms_path, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        self.symptoms.append({
                            'id': row.get('symptom_id', ''),
                            'name': row.get('symptom_name', '').strip().lower(),
                            'name_te': row.get('symptom_name_te', '').strip(),
                            'category': row.get('category', '').strip(),
                            'severity': row.get('severity', 'mild').strip().lower(),
                            'body_part': row.get('body_part', 'general').strip().lower(),
                            'description': row.get('description', '').strip()
                        })
            except Exception as e:
                print(f"Warning: Failed to load symptoms.csv: {e}")
                
        # Load English mappings
        english_path = os.path.join(self.dataset_dir, 'english.csv')
        if os.path.exists(english_path):
            try:
                with open(english_path, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        self.english_mappings.append({
                            'phrase': row.get('phrase', '').strip().lower(),
                            'standard': row.get('standard', '').strip().lower(),
                            'category': row.get('category', 'symptom').strip().lower()
                        })
            except Exception as e:
                print(f"Warning: Failed to load english.csv: {e}")
                
        # Load diseases
        diseases_path = os.path.join(self.dataset_dir, 'diseases.csv')
        if os.path.exists(diseases_path):
            try:
                with open(diseases_path, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Parse symptoms list
                        symptom_list = [s.strip().lower() for s in row.get('common_symptoms', '').split(',') if s.strip()]
                        self.diseases.append({
                            'id': row.get('disease_id', ''),
                            'name': row.get('disease_name', '').strip().lower(),
                            'name_te': row.get('disease_name_te', '').strip(),
                            'symptoms': symptom_list,
                            'department': row.get('department', '').strip(),
                            'severity': row.get('severity', 'medium').strip().lower(),
                            'description': row.get('description', '').strip()
                        })
            except Exception as e:
                print(f"Warning: Failed to load diseases.csv: {e}")

    def _init_model(self):
        try:
            # Lazy load model using a lightweight sentence-transformer model
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self._load_symptom_embeddings()
        except Exception as e:
            print(f"Warning: Failed to initialize SentenceTransformer model: {e}. Falling back to keyword matching.")
            self.model = None

    def _load_symptom_embeddings(self):
        if not self.model:
            return
            
        try:
            # Precompute embeddings for standard symptoms
            symptom_names = [s['name'] for s in self.symptoms]
            if symptom_names:
                self.symptom_embeddings = self.model.encode(symptom_names, convert_to_tensor=True)
                
            # Precompute embeddings for English colloquial mappings
            mapping_phrases = [m['phrase'] for m in self.english_mappings]
            if mapping_phrases:
                self.mapping_embeddings = self.model.encode(mapping_phrases, convert_to_tensor=True)
        except Exception as e:
            print(f"Warning: Failed to precompute embeddings: {e}. Falling back to keyword matching.")
            self.model = None

    def extract_symptoms(self, text: str, confidence_threshold=0.6) -> list:
        """
        Extract symptoms from the user's English (or translated-to-English) text query.
        Returns a list of dicts: [{'name': 'headache', 'confidence': 0.85, 'category': 'neurological'}]
        """
        if not text or not text.strip():
            return []
            
        text_lower = text.lower().strip()
        extracted = {}
        
        # 1. Semantic Matching (SentenceTransformers)
        if self.model and self.symptom_embeddings is not None:
            try:
                # Segment input text into simple clauses/phrases
                clauses = [c.strip() for c in re.split(r'[,.!?and;]|\bbut\b', text_lower) if c.strip()]
                if not clauses:
                    clauses = [text_lower]
                    
                for clause in clauses:
                    clause_embedding = self.model.encode(clause, convert_to_tensor=True)
                    
                    # Match against standard symptoms
                    symptom_cos_scores = util.cos_sim(clause_embedding, self.symptom_embeddings)[0]
                    for idx, score in enumerate(symptom_cos_scores):
                        val = float(score.item())
                        if val >= confidence_threshold:
                            s_name = self.symptoms[idx]['name']
                            s_cat = self.symptoms[idx]['category']
                            if s_name not in extracted or val > extracted[s_name]['confidence']:
                                extracted[s_name] = {
                                    'name': s_name,
                                    'confidence': round(val, 2),
                                    'category': s_cat
                                }
                                
                    # Match against colloquial mappings
                    if self.mapping_embeddings is not None:
                        mapping_cos_scores = util.cos_sim(clause_embedding, self.mapping_embeddings)[0]
                        for idx, score in enumerate(mapping_cos_scores):
                            val = float(score.item())
                            if val >= confidence_threshold:
                                standard_name = self.english_mappings[idx]['standard']
                                # Find category for the standard symptom
                                s_cat = 'general'
                                for s in self.symptoms:
                                    if s['name'] == standard_name:
                                        s_cat = s['category']
                                        break
                                if standard_name not in extracted or val > extracted[standard_name]['confidence']:
                                    extracted[standard_name] = {
                                        'name': standard_name,
                                        'confidence': round(val, 2),
                                        'category': s_cat
                                    }
            except Exception as e:
                print(f"Error during semantic symptom extraction: {e}. Falling back to keywords.")
                
        # 2. Keyword/Substring Fallback (Regex-based)
        # We always run this to capture exact keyword matches which might score slightly below threshold semantically
        for item in self.symptoms:
            name = item['name']
            escaped_name = re.escape(name)
            # Match whole word/phrase
            if re.search(rf'\b{escaped_name}\b', text_lower):
                if name not in extracted:
                    extracted[name] = {
                        'name': name,
                        'confidence': 1.0,
                        'category': item['category']
                    }
                    
        for item in self.english_mappings:
            phrase = item['phrase']
            standard = item['standard']
            escaped_phrase = re.escape(phrase)
            if re.search(rf'\b{escaped_phrase}\b', text_lower):
                if standard not in extracted:
                    # Find category
                    s_cat = 'general'
                    for s in self.symptoms:
                        if s['name'] == standard:
                            s_cat = s['category']
                            break
                    extracted[standard] = {
                        'name': standard,
                        'confidence': 1.0,
                        'category': s_cat
                    }
                    
        return list(extracted.values())

    def get_missing_symptoms(self, extracted_names: list, max_questions=3) -> list:
        """
        Identify symptoms commonly co-occurring with the extracted symptoms in diseases.csv
        that the user has not reported yet.
        """
        if not extracted_names:
            return []
            
        extracted_set = set(extracted_names)
        potential_diseases = []
        
        # Find diseases that share at least one extracted symptom
        for disease in self.diseases:
            disease_symptoms = set(disease['symptoms'])
            intersect = disease_symptoms.intersection(extracted_set)
            if intersect:
                # Store disease and number of matching symptoms
                potential_diseases.append((disease, len(intersect)))
                
        # Sort potential diseases by number of matches descending
        potential_diseases.sort(key=lambda x: x[1], reverse=True)
        
        missing_symptoms_counts = {}
        for disease, _ in potential_diseases[:3]:  # Look at top 3 candidate diseases
            for s in disease['symptoms']:
                if s not in extracted_set:
                    missing_symptoms_counts[s] = missing_symptoms_counts.get(s, 0) + 1
                    
        # Sort missing symptoms by frequency of co-occurrence
        sorted_missing = sorted(missing_symptoms_counts.items(), key=lambda x: x[1], reverse=True)
        return [item[0] for item in sorted_missing[:max_questions]]

    def generate_followup_question(self, missing_symptoms: list, language='en') -> str:
        """
        Builds a conversational question checking for missing symptoms.
        """
        if not missing_symptoms:
            return ""
            
        # Get Telugu names for the missing symptoms
        symptom_display_names = []
        for ms in missing_symptoms:
            found = False
            for s in self.symptoms:
                if s['name'] == ms:
                    if language == 'te' and s['name_te']:
                        symptom_display_names.append(s['name_te'])
                    else:
                        symptom_display_names.append(s['name'])
                    found = True
                    break
            if not found:
                symptom_display_names.append(ms)

        if len(symptom_display_names) == 1:
            term = symptom_display_names[0]
            if language == 'te':
                return f"మీకు {term} కూడా ఉందా? (అవును / లేదు)"
            else:
                return f"Are you also experiencing {term}? (Yes / No)"
        elif len(symptom_display_names) == 2:
            t1, t2 = symptom_display_names[0], symptom_display_names[1]
            if language == 'te':
                return f"మీకు {t1} లేదా {t2} వంటి లక్షణాలు కూడా ఉన్నాయా? (అవును / లేదు)"
            else:
                return f"Are you also experiencing {t1} or {t2}? (Yes / No)"
        else:
            list_str = ", ".join(symptom_display_names[:-1]) + f" or {symptom_display_names[-1]}"
            if language == 'te':
                list_str_te = ", ".join(symptom_display_names[:-1]) + f" లేదా {symptom_display_names[-1]}"
                return f"మీకు ఈ క్రింది లక్షణాలలో ఏవైనా ఉన్నాయా: {list_str_te}? (అవును / లేదు)"
            else:
                return f"Are you experiencing any of the following symptoms: {list_str}? (Yes / No)"
