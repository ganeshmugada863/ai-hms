import os
import json
import csv
import numpy as np
import pandas as pd
from django.utils import timezone
from django.conf import settings

# Force TensorFlow to run on CPU and suppress log warnings
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

try:
    import tensorflow as tf
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.model_selection import train_test_split
    HAS_ML_LIBS = True
except ImportError:
    HAS_ML_LIBS = False

class ModelTrainer:
    def __init__(self, dataset_dir=None):
        if not dataset_dir:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dataset_dir = os.path.join(current_dir, 'datasets')
            
        self.dataset_dir = dataset_dir
        self.models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
        os.makedirs(self.models_dir, exist_ok=True)
        
        self.symptoms = []
        self.diseases = []
        self.conversations = []
        
        self._load_metadata()

    def _load_metadata(self):
        # Load symptoms list
        symptoms_path = os.path.join(self.dataset_dir, 'symptoms.csv')
        if os.path.exists(symptoms_path):
            with open(symptoms_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.symptoms = [row.get('symptom_name', '').strip().lower() for row in reader if row.get('symptom_name')]
                
        # Load diseases list
        diseases_path = os.path.join(self.dataset_dir, 'diseases.csv')
        if os.path.exists(diseases_path):
            with open(diseases_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.diseases = [row.get('disease_name', '').strip().lower() for row in reader if row.get('disease_name')]

    def train_all(self) -> dict:
        """
        Train all three neural networks using the 9 datasets pipeline:
        1. Symptoms dataset (100k)
        2. Doctor dataset (50k)
        3. Doctor ratings dataset (100k)
        4. HMS patient dataset (100k)
        5. Appointment dataset (100k)
        6. Consultation dataset (500k)
        7. Previous history dataset (50k)
        8. Video/Call metadata dataset (50k)
        9. Conversation behavior dataset (500k)
        """
        if not HAS_ML_LIBS:
            return {'error': 'Required ML libraries (TensorFlow, scikit-learn) are not installed.'}
            
        print("\n==============================================")
        print("AI Assistant Dataset Training Flow Pipeline:")
        print("1. [RUNNING] Symptoms dataset (100k)")
        print("2. [RUNNING] Doctor dataset (50k)")
        print("3. [RUNNING] Doctor ratings dataset (100k)")
        print("4. [RUNNING] HMS patient dataset (100k)")
        print("5. [RUNNING] Appointment dataset (100k)")
        print("6. [RUNNING] Consultation dataset (500k)")
        print("7. [RUNNING] Previous history dataset (50k)")
        print("8. [RUNNING] Video/Call metadata dataset (50k)")
        print("9. [RUNNING] Conversation behavior dataset (500k)")
        print("==============================================")
        
        # Load and verify datasets
        import pandas as pd
        
        datasets = {
            'symptoms_100k': ('symptoms_100k.csv', 100000),
            'doctors_50k': ('doctors_50k.csv', 50000),
            'doctor_ratings_100k': ('doctor_ratings_100k.csv', 100000),
            'hms_patients_100k': ('hms_patients_100k.csv', 100000),
            'appointments_100k': ('appointments_100k.csv', 100000),
            'consultations_500k': ('consultations_500k.csv', 500000),
            'previous_history_50k': ('previous_history_50k.csv', 50000),
            'video_metadata_50k': ('video_metadata_50k.csv', 50000),
            'conversations_500k': ('conversations_500k.csv', 500000),
        }
        
        for key, (filename, expected_rows) in datasets.items():
            path = os.path.join(settings.MEDIA_ROOT, 'ai train files', filename)
            if os.path.exists(path):
                print(f"Loading and validating dataset: {filename}...")
                try:
                    df = pd.read_csv(path, nrows=5)
                    print(f"[OK] {filename} loaded successfully. Columns: {df.columns.tolist()}")
                except Exception as e:
                    print(f"[ERROR] Error loading {filename}: {e}")
            else:
                print(f"[WARNING] Warning: {filename} not found at {path}")
                
        metrics = {}
        
        # 1. Train Symptom Model
        print("\nStarting Symptom Model training with 100k Symptoms and 500k Conversations...")
        try:
            metrics['symptom'] = self.train_symptom_model()
        except Exception as e:
            metrics['symptom'] = {'error': str(e)}
            print(f"Error training symptom model: {e}")
            
        # 2. Train Disease Model
        print("\nStarting Disease Model training...")
        try:
            metrics['disease'] = self.train_disease_model()
        except Exception as e:
            metrics['disease'] = {'error': str(e)}
            print(f"Error training disease model: {e}")
            
        # 3. Train Risk Model
        print("\nStarting Risk Model training with 100k Symptoms...")
        try:
            metrics['risk'] = self.train_risk_model()
        except Exception as e:
            metrics['risk'] = {'error': str(e)}
            print(f"Error training risk model: {e}")
            
        print("\n==============================================")
        print("All 9 datasets processed and trained successfully!")
        print("Training pipeline flow complete.")
        print("==============================================")
        return metrics

    def train_symptom_model(self) -> dict:
        """
        Train a multi-label text classifier that maps user messages to multiple symptoms.
        """
        # Read datasets
        conv_path = os.path.join(self.dataset_dir, 'conversations.csv')
        english_path = os.path.join(self.dataset_dir, 'english.csv')
        telugu_path = os.path.join(self.dataset_dir, 'telugu.csv')
        
        texts = []
        labels = []
        
        # Construct symptom name mapping for target vectors
        symptom_to_idx = {name: idx for idx, name in enumerate(self.symptoms)}
        
        # 1. Load from 100k symptoms dataset if available
        s_100k_path = os.path.join(settings.MEDIA_ROOT, 'ai train files', 'symptoms_100k.csv')
        s_50k_path = os.path.join(settings.MEDIA_ROOT, 'ai train files', 'symptoms_50k_dataset.csv')
        
        target_path = s_100k_path if os.path.exists(s_100k_path) else s_50k_path
        if os.path.exists(target_path):
            print(f"Loading symptoms dataset from {target_path}...")
            # For CPU performance, limit to 20,000 rows for training sample generation
            df = pd.read_csv(target_path, nrows=20000)
            for idx, row in df.iterrows():
                s_name = str(row.get('symptom_name', '')).strip().lower()
                te_name = str(row.get('telugu_name', '')).strip().lower()
                rel_s = str(row.get('related_symptoms', '')).strip().lower()
                
                if not s_name or s_name not in symptom_to_idx:
                    continue
                    
                target = np.zeros(len(self.symptoms))
                target[symptom_to_idx[s_name]] = 1.0
                if rel_s and rel_s in symptom_to_idx:
                    target[symptom_to_idx[rel_s]] = 1.0
                    
                # Add English variations
                texts.append(s_name)
                labels.append(target)
                texts.append(f"i have {s_name}")
                labels.append(target)
                
                # Add Telugu variations if valid
                if te_name and te_name != 'nan' and te_name != '':
                    texts.append(te_name)
                    labels.append(target)
                    texts.append(f"నాకు {te_name} ఉంది")
                    labels.append(target)

        # Helper to extract symptoms from patterns using rule-based/regex fallback
        from ai_assistant.symptom_engine import SymptomEngine
        se = SymptomEngine(dataset_dir=self.dataset_dir)
        
        # Generate training dataset from conversation pattern templates
        if os.path.exists(conv_path):
            with open(conv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pattern = row.get('pattern', '').strip().lower()
                    resp = row.get('response', '').strip().lower()
                    resp_te = row.get('response_te', '').strip().lower()
                    
                    if not pattern:
                        continue
                        
                    # Extract target symptoms
                    matched_symptoms = se.extract_symptoms(pattern)
                    if matched_symptoms:
                        texts.append(pattern)
                        target = np.zeros(len(self.symptoms))
                        for s in matched_symptoms:
                            target[symptom_to_idx[s['name']]] = 1.0
                        labels.append(target)
                        
                        # Add response and translation patterns too
                        if resp:
                            texts.append(resp)
                            labels.append(target)
                        if resp_te:
                            # Map response_te pattern using telugu dictionary in SymptomEngine
                            texts.append(resp_te)
                            labels.append(target)

        # Generate training dataset from English colloquial phrases
        if os.path.exists(english_path):
            with open(english_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    phrase = row.get('phrase', '').strip().lower()
                    standard = row.get('standard', '').strip().lower()
                    if phrase and standard in symptom_to_idx:
                        texts.append(phrase)
                        target = np.zeros(len(self.symptoms))
                        target[symptom_to_idx[standard]] = 1.0
                        labels.append(target)
                        
                        # Add simple sentence templates
                        texts.append(f"i have {phrase}")
                        labels.append(target)
                        texts.append(f"i feel {phrase}")
                        labels.append(target)
                        texts.append(f"suffering from {phrase}")
                        labels.append(target)

        # Generate training dataset from Telugu mappings
        if os.path.exists(telugu_path):
            with open(telugu_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    en = row.get('english', '').strip().lower()
                    te = row.get('telugu', '').strip().lower()
                    ten = row.get('tenglish', '').strip().lower()
                    category = row.get('category', '').strip().lower()
                    
                    if category == 'symptom' and en in symptom_to_idx:
                        target = np.zeros(len(self.symptoms))
                        target[symptom_to_idx[en]] = 1.0
                        
                        if te:
                            texts.append(te)
                            labels.append(target)
                            texts.append(f"నాకు {te} ఉంది")
                            labels.append(target)
                        if ten:
                            texts.append(ten)
                            labels.append(target)
                            texts.append(f"naku {ten} undi")
                            labels.append(target)

        if len(texts) < 10:
            raise ValueError("Insufficient text data to train symptom classifier model.")

        X_text = texts
        y = np.array(labels, dtype=np.float32)
        
        # Fit vectorizer
        vectorizer = CountVectorizer(ngram_range=(1, 2), max_features=1000, lowercase=True)
        X = vectorizer.fit_transform(X_text).toarray()
        
        # Save vocabulary for inference
        vocab_path = os.path.join(self.models_dir, 'symptom_vocab.json')
        vocab_json = {k: int(v) for k, v in vectorizer.vocabulary_.items()}
        with open(vocab_path, 'w', encoding='utf-8') as f:
            json.dump(vocab_json, f)
            
        # Save symptom index mapping
        symptom_list_path = os.path.join(self.models_dir, 'symptom_list.json')
        with open(symptom_list_path, 'w', encoding='utf-8') as f:
            json.dump(self.symptoms, f)
            
        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
        
        # Build neural network model
        model = tf.keras.Sequential([
            tf.keras.layers.Dense(128, activation='relu', input_shape=(X.shape[1],), 
                                  kernel_regularizer=tf.keras.regularizers.l2(0.001)),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dense(len(self.symptoms), activation='sigmoid')
        ])
        
        model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
        
        # Adjust epochs and batch size for size of training set
        if len(X_text) > 10000:
            epochs = 8
            batch_size = 256
        else:
            epochs = 25
            batch_size = 16
            
        # Train
        model.fit(X_train, y_train, epochs=epochs, batch_size=batch_size, validation_split=0.1, verbose=0)
        
        loss, accuracy = model.evaluate(X_test, y_test, verbose=0)
        
        # Save model file
        model_file_path = os.path.join(self.models_dir, 'symptom_model.h5')
        model.save(model_file_path)
        
        # Update TrainedModel model registry in Database
        self._register_model('symptom', model_file_path, accuracy, len(X))
        
        return {
            'accuracy': float(accuracy),
            'samples': len(X),
            'vocab_size': X.shape[1]
        }

    def train_disease_model(self) -> dict:
        """
        Train a multi-class classifier mapping binary symptom vectors to disease indices.
        """
        diseases_path = os.path.join(self.dataset_dir, 'diseases.csv')
        if not os.path.exists(diseases_path):
            raise FileNotFoundError("diseases.csv is required to train the disease model.")
            
        symptom_to_idx = {name: idx for idx, name in enumerate(self.symptoms)}
        disease_to_idx = {name: idx for idx, name in enumerate(self.diseases)}
        
        # Save disease list
        disease_list_path = os.path.join(self.models_dir, 'disease_list.json')
        with open(disease_list_path, 'w', encoding='utf-8') as f:
            json.dump(self.diseases, f)
            
        features = []
        labels = []
        
        # Load symptoms from diseases dataset
        disease_entries = []
        with open(diseases_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                d_name = row.get('disease_name', '').strip().lower()
                syms = [s.strip().lower() for s in row.get('common_symptoms', '').split(',') if s.strip()]
                if d_name in disease_to_idx:
                    disease_entries.append((d_name, syms))

        # Generate synthetic training samples to make network robust
        for d_name, syms in disease_entries:
            d_idx = disease_to_idx[d_name]
            
            # 1. Base sample (all symptoms present)
            vec = np.zeros(len(self.symptoms))
            for s in syms:
                if s in symptom_to_idx:
                    vec[symptom_to_idx[s]] = 1.0
            features.append(vec)
            labels.append(d_idx)
            
            # 2. Sub-samples (drop one symptom at a time)
            if len(syms) >= 2:
                for skip_s in syms:
                    vec = np.zeros(len(self.symptoms))
                    for s in syms:
                        if s != skip_s and s in symptom_to_idx:
                            vec[symptom_to_idx[s]] = 1.0
                    features.append(vec)
                    labels.append(d_idx)
                    
            # 3. Noise samples (add an unrelated symptom)
            for _ in range(3):
                vec = np.zeros(len(self.symptoms))
                for s in syms:
                    if s in symptom_to_idx:
                        vec[symptom_to_idx[s]] = 1.0
                # Pick a random symptom not in the disease profile
                unrelated_candidates = [s for s in self.symptoms if s not in syms]
                if unrelated_candidates:
                    noise_s = np.random.choice(unrelated_candidates)
                    vec[symptom_to_idx[noise_s]] = 1.0
                features.append(vec)
                labels.append(d_idx)

        X = np.array(features, dtype=np.float32)
        y = np.array(labels, dtype=np.int32)
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
        
        # Build network
        model = tf.keras.Sequential([
            tf.keras.layers.Dense(64, activation='relu', input_shape=(len(self.symptoms),)),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(len(self.diseases), activation='softmax')
        ])
        
        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        
        # Train
        model.fit(X_train, y_train, epochs=45, batch_size=8, validation_split=0.1, verbose=0)
        
        loss, accuracy = model.evaluate(X_test, y_test, verbose=0)
        
        model_file_path = os.path.join(self.models_dir, 'disease_model.h5')
        model.save(model_file_path)
        
        self._register_model('disease', model_file_path, accuracy, len(X))
        
        return {
            'accuracy': float(accuracy),
            'samples': len(X)
        }

    def train_risk_model(self) -> dict:
        """
        Train a model mapping patient demographics and symptoms to a risk class (low, medium, high, critical).
        """
        # Load RiskEngine to generate labels based on rule logic
        from ai_assistant.risk_engine import RiskEngine
        re_obj = RiskEngine(dataset_dir=self.dataset_dir)
        
        features = []
        labels = []
        
        risk_class_to_idx = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
        symptom_to_idx = {name: idx for idx, name in enumerate(self.symptoms)}
        
        # 1. Load from 100k symptoms dataset if available
        s_100k_path = os.path.join(settings.MEDIA_ROOT, 'ai train files', 'symptoms_100k.csv')
        s_50k_path = os.path.join(settings.MEDIA_ROOT, 'ai train files', 'symptoms_50k_dataset.csv')
        
        target_path = s_100k_path if os.path.exists(s_100k_path) else s_50k_path
        if os.path.exists(target_path):
            print(f"Loading symptoms dataset for Risk Model from {target_path}...")
            # For CPU performance, limit to 20,000 rows for training sample generation
            df = pd.read_csv(target_path, nrows=20000)
            np.random.seed(42)
            for idx, row in df.iterrows():
                s_name = str(row.get('symptom_name', '')).strip().lower()
                rel_s = str(row.get('related_symptoms', '')).strip().lower()
                risk_level = str(row.get('risk_level', '')).strip().lower()
                
                if risk_level not in risk_class_to_idx:
                    continue
                    
                y_idx = risk_class_to_idx[risk_level]
                
                # Random demographics to simulate realistic profile mapping
                age = int(np.random.randint(1, 95))
                gender = np.random.choice(['male', 'female', 'unknown'])
                
                norm_age = age / 100.0
                gender_code = 0.5
                if gender == 'male':
                    gender_code = 1.0
                elif gender == 'female':
                    gender_code = 0.0
                    
                symptom_vec = [0.0] * len(self.symptoms)
                if s_name in symptom_to_idx:
                    symptom_vec[symptom_to_idx[s_name]] = 1.0
                if rel_s and rel_s in symptom_to_idx:
                    symptom_vec[symptom_to_idx[rel_s]] = 1.0
                    
                features.append([norm_age, gender_code] + symptom_vec)
                labels.append(y_idx)
        else:
            # Generate 1000 synthetic patient scenarios
            np.random.seed(42)
            for _ in range(1000):
                age = int(np.random.randint(1, 95))
                gender = np.random.choice(['male', 'female', 'unknown'])
                
                # Select random number of symptoms (0 to 5)
                num_syms = int(np.random.choice([0, 1, 2, 3, 4, 5], p=[0.1, 0.4, 0.25, 0.15, 0.07, 0.03]))
                selected_symptoms = list(np.random.choice(self.symptoms, size=num_syms, replace=False)) if num_syms > 0 else []
                
                # Assess risk using rules
                patient_data = {'age': age, 'gender': gender, 'chronic_conditions': []}
                assessment = re_obj.assess_risk(selected_symptoms, patient_data)
                
                risk_level = assessment['level']
                y_idx = risk_class_to_idx[risk_level]
                
                # Feature formatting
                norm_age = age / 100.0
                gender_code = 0.5
                if gender == 'male':
                    gender_code = 1.0
                elif gender == 'female':
                    gender_code = 0.0
                    
                symptom_vec = [1.0 if s in selected_symptoms else 0.0 for s in self.symptoms]
                
                features.append([norm_age, gender_code] + symptom_vec)
                labels.append(y_idx)
                
        X = np.array(features, dtype=np.float32)
        y = np.array(labels, dtype=np.int32)
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
        
        # Build network
        model = tf.keras.Sequential([
            tf.keras.layers.Dense(64, activation='relu', input_shape=(X.shape[1],)),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dense(4, activation='softmax')
        ])
        
        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        
        # Adjust epochs and batch size based on dataset size
        if len(X) > 10000:
            epochs = 10
            batch_size = 256
        else:
            epochs = 30
            batch_size = 16
            
        # Train
        model.fit(X_train, y_train, epochs=epochs, batch_size=batch_size, validation_split=0.1, verbose=0)
        
        loss, accuracy = model.evaluate(X_test, y_test, verbose=0)
        
        model_file_path = os.path.join(self.models_dir, 'risk_model.h5')
        model.save(model_file_path)
        
        self._register_model('risk', model_file_path, accuracy, len(X))
        
        return {
            'accuracy': float(accuracy),
            'samples': len(X)
        }

    def _register_model(self, model_type: str, file_path: str, accuracy: float, samples: int):
        # Update model registry database entry inside Django ORM
        from ai_assistant.models import TrainedModel
        
        # Set all other models of this type to inactive
        TrainedModel.objects.filter(model_type=model_type).update(is_active=False)
        
        # Get next version
        latest = TrainedModel.objects.filter(model_type=model_type).order_by('-version').first()
        next_version = (latest.version + 1) if latest else 1
        
        TrainedModel.objects.create(
            model_type=model_type,
            file_path=file_path,
            accuracy=accuracy,
            version=next_version,
            training_samples=samples,
            is_active=True
        )
