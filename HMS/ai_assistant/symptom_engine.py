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
        self.symptoms = []
        self.english_mappings = []
        self.diseases = []
        self.model = None
        self.symptom_embeddings = None
        self.mapping_embeddings = None
        
        if not dataset_dir:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dataset_dir = os.path.join(current_dir, 'datasets')
            
        self.dataset_dir = dataset_dir
        
        # Ensure datasets directory exists
        if not os.path.exists(self.dataset_dir):
            os.makedirs(self.dataset_dir)
            
        self._ensure_default_datasets()
        self._load_datasets()
        
        if HAS_TRANSFORMERS:
            self._init_model()

    def _ensure_default_datasets(self):
        # 1. symptoms.csv
        symptoms_path = os.path.join(self.dataset_dir, 'symptoms.csv')
        if not os.path.exists(symptoms_path):
            with open(symptoms_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['symptom_id', 'symptom_name', 'symptom_name_te', 'category', 'severity', 'body_part', 'description'])
                writer.writerows([
                    ['1', 'chest pain', 'ఛాతి నొప్పి', 'cardiovascular', 'high', 'chest', 'Pain or pressure in the chest area'],
                    ['2', 'skin rash', 'చర్మంపై దద్దుర్లు', 'dermatological', 'mild', 'skin', 'Red, itchy bumps or dry skin patches'],
                    ['3', 'eye pain', 'కంటి నొప్పి', 'ophthalmological', 'medium', 'eyes', 'Soreness, irritation or redness in eyes'],
                    ['4', 'ear pain', 'చెవి నొప్పి', 'ent', 'mild', 'ears', 'Pain or throbbing sensation inside the ear'],
                    ['5', 'tooth pain', 'పంటి నొప్పి', 'dental', 'mild', 'mouth', 'Toothache or sensitive gums'],
                    ['6', 'joint pain', 'కీళ్ల నొప్పులు', 'musculoskeletal', 'medium', 'joints', 'Stiffness, swelling or pain in joints'],
                    ['7', 'pregnancy', 'గర్భం', 'gynecological', 'medium', 'pelvis', 'Missed periods, nausea or prenatal support'],
                    ['8', 'child health', 'పిల్లల జ్వరం', 'pediatric', 'medium', 'general', 'General wellness for pediatric patients'],
                    ['9', 'mental stress', 'మానసిక ఒత్తిడి', 'psychiatric', 'medium', 'brain', 'Anxiety, sleep issues, or depression'],
                    ['10', 'stomach pain', 'కడుపు నొప్పి', 'gastrointestinal', 'medium', 'abdomen', 'Acidity, stomach ache, bloating or nausea'],
                    ['11', 'kidney pain', 'మూత్రపిండాల నొప్పి', 'renal', 'high', 'back', 'Flank pain or burning urination'],
                    ['12', 'breathing difficulty', 'శ్వాస తీసుకోవడంలో ఇబ్బంది', 'respiratory', 'high', 'lungs', 'Shortness of breath, wheezing, or dry cough'],
                    ['13', 'fever', 'జ్వరం', 'general', 'medium', 'general', 'High body temperature or flu symptoms'],
                    ['14', 'headache', 'తలనొప్పి', 'neurological', 'medium', 'head', 'Migraine or tension headaches']
                ])

        # 2. english.csv (colloquial mapping)
        english_path = os.path.join(self.dataset_dir, 'english.csv')
        if not os.path.exists(english_path):
            with open(english_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['phrase', 'standard', 'category'])
                writer.writerows([
                    ['heart hurts', 'chest pain', 'symptom'],
                    ['chest hurts', 'chest pain', 'symptom'],
                    ['stomach hurts', 'stomach pain', 'symptom'],
                    ['rash on skin', 'skin rash', 'symptom'],
                    ['eyes hurt', 'eye pain', 'symptom'],
                    ['toothache', 'tooth pain', 'symptom'],
                    ['back hurts', 'joint pain', 'symptom'],
                    ['missed period', 'pregnancy', 'symptom'],
                    ['child sick', 'child health', 'symptom'],
                    ['feeling depressed', 'mental stress', 'symptom'],
                    ['kidney hurts', 'kidney pain', 'symptom'],
                    ['short of breath', 'breathing difficulty', 'symptom'],
                    ['high temp', 'fever', 'symptom'],
                    ['head hurts', 'headache', 'symptom'],
                    ['nauseous', 'stomach pain', 'symptom'],
                    ['coughing', 'breathing difficulty', 'symptom']
                ])

        # 3. diseases.csv
        diseases_path = os.path.join(self.dataset_dir, 'diseases.csv')
        if not os.path.exists(diseases_path):
            with open(diseases_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['disease_id', 'disease_name', 'disease_name_te', 'common_symptoms', 'department', 'severity', 'description'])
                writer.writerows([
                    ['1', 'Angina Pectoris', 'గుండె జబ్బు', 'chest pain,breathing difficulty', 'Cardiology', 'high', 'Coronary artery condition causing chest pain'],
                    ['2', 'Contact Dermatitis', 'చర్మ వ్యాధి', 'skin rash', 'Dermatology', 'mild', 'Skin inflammation due to contact with allergy triggers'],
                    ['3', 'Conjunctivitis', 'కండ్లకలక', 'eye pain', 'Ophthalmology', 'medium', 'Pink eye infection causing pain and redness'],
                    ['4', 'Otitis Media', 'చెవి ఇన్ఫెక్షన్', 'ear pain,fever', 'ENT', 'mild', 'Middle ear infection common in children'],
                    ['5', 'Dental Caries', 'పంటి పుచ్చు', 'tooth pain', 'Dentistry', 'mild', 'Tooth decay causing sensitivity and cavities'],
                    ['6', 'Osteoarthritis', 'కీళ్ల వాతము', 'joint pain', 'Orthopedics', 'medium', 'Degenerative joint disease causing stiffness'],
                    ['7', 'Pregnancy Care', 'గర్భధారణ సంరక్షణ', 'pregnancy', 'Gynecology', 'medium', 'Prenatal health monitoring and routine checks'],
                    ['8', 'Pediatric Flu', 'పిల్లల జ్వరం', 'child health,fever', 'Pediatrics', 'medium', 'Viral infections in young infants and children'],
                    ['9', 'General Anxiety Disorder', 'ఆందోళన', 'mental stress', 'Psychiatry', 'medium', 'Excessive anxiety and stress interference'],
                    ['10', 'Acute Gastroenteritis', 'కడుపు ఇన్ఫెక్షన్', 'stomach pain', 'Gastroenterology', 'medium', 'Stomach flu causing cramps and nausea'],
                    ['11', 'Urinary Tract Infection', 'యూరినరీ ట్రాక్ట్ ఇన్ఫెక్షన్', 'kidney pain,fever', 'Nephrology', 'high', 'Infection inside the renal tract causing pain'],
                    ['12', 'Asthma Bronchiale', 'అస్తమా', 'breathing difficulty', 'Pulmonology', 'high', 'Chronic respiratory disease causing breathlessness'],
                    ['13', 'Influenza', 'సరి జ్వరం', 'fever,headache', 'General Physician', 'medium', 'Seasonal flu infection with fever and body aches'],
                    ['14', 'Migraine', 'తలనొప్పి', 'headache', 'Neurology', 'medium', 'Severe throbbing headache, often one-sided']
                ])

    def _load_datasets(self):
        # Symptoms
        symptoms_path = os.path.join(self.dataset_dir, 'symptoms.csv')
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
                
        # English mappings
        english_path = os.path.join(self.dataset_dir, 'english.csv')
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
                
        # Diseases
        diseases_path = os.path.join(self.dataset_dir, 'diseases.csv')
        try:
            with open(diseases_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
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
            # Force CPU usage to prevent GPU overhead / CUDA conflicts
            self.model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
            self._load_symptom_embeddings()
        except Exception as e:
            print(f"Warning: Failed to initialize SentenceTransformer model: {e}. Falling back to keywords.")
            self.model = None

    def _load_symptom_embeddings(self):
        if not self.model:
            return
        try:
            symptom_names = [s['name'] for s in self.symptoms]
            if symptom_names:
                self.symptom_embeddings = self.model.encode(symptom_names, convert_to_tensor=True, device='cpu')
                
            mapping_phrases = [m['phrase'] for m in self.english_mappings]
            if mapping_phrases:
                self.mapping_embeddings = self.model.encode(mapping_phrases, convert_to_tensor=True, device='cpu')
        except Exception as e:
            print(f"Warning: Failed to precompute embeddings: {e}. Falling back to keywords.")
            self.model = None

    def extract_symptoms(self, text: str, confidence_threshold=0.6) -> list:
        if not text or not text.strip():
            return []
            
        text_lower = text.lower().strip()
        extracted = {}
        
        # 1. Semantic Matching (SentenceTransformers on CPU)
        if self.model and self.symptom_embeddings is not None:
            try:
                clauses = [c.strip() for c in re.split(r'[,.!?and;]|\bbut\b', text_lower) if c.strip()]
                if not clauses:
                    clauses = [text_lower]
                    
                for clause in clauses:
                    clause_embedding = self.model.encode(clause, convert_to_tensor=True, device='cpu')
                    
                    # Match standard symptoms
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
                                
                    # Match English mappings
                    if self.mapping_embeddings is not None:
                        mapping_cos_scores = util.cos_sim(clause_embedding, self.mapping_embeddings)[0]
                        for idx, score in enumerate(mapping_cos_scores):
                            val = float(score.item())
                            if val >= confidence_threshold:
                                standard_name = self.english_mappings[idx]['standard']
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
                print(f"Error during semantic symptom extraction: {e}")
                
        # 2. Substring Fallback
        for item in self.symptoms:
            name = item['name']
            escaped_name = re.escape(name)
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
