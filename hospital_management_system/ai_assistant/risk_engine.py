import os
import csv
import numpy as np

class RiskEngine:
    def __init__(self, dataset_dir=None):
        self.symptoms = []
        self.model = None
        self.model_loaded = False
        
        if not dataset_dir:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dataset_dir = os.path.join(current_dir, 'datasets')
            
        self.dataset_dir = dataset_dir
        self._load_symptoms()
        self._load_model()

    def _load_symptoms(self):
        symptoms_path = os.path.join(self.dataset_dir, 'symptoms.csv')
        if os.path.exists(symptoms_path):
            try:
                with open(symptoms_path, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        self.symptoms.append({
                            'name': row.get('symptom_name', '').strip().lower(),
                            'severity': row.get('severity', 'mild').strip().lower(),
                            'category': row.get('category', '').strip()
                        })
            except Exception as e:
                print(f"Warning: Failed to load symptoms in RiskEngine: {e}")

    def _load_model(self):
        # Lazily check and load the model file if it exists
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(current_dir, 'models', 'risk_model.h5')
        if os.path.exists(model_path):
            try:
                import tensorflow as tf
                # Disable GPU messages for CPU-only environments
                os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
                self.model = tf.keras.models.load_model(model_path)
                self.model_loaded = True
            except Exception as e:
                print(f"Warning: Failed to load risk_model.h5: {e}. Using rule-based fallback.")
                self.model = None

    def assess_risk(self, extracted_symptoms: list, patient_data: dict) -> dict:
        """
        Assess risk level for the patient.
        patient_data should be: {'age': 45, 'gender': 'male', 'chronic_conditions': [...]}
        extracted_symptoms: list of symptom names e.g., ['cough', 'chest pain']
        """
        symptom_names = [s.strip().lower() for s in extracted_symptoms]
        
        # Check critical emergency symptoms first
        emergency_keywords = [
            'chest pain', 'shortness of breath', 'breathing difficulty', 
            'unconscious', 'seizure', 'stroke', 'severe bleeding', 
            'chest tightness', 'blood in sputum', 'blood in urine', 
            'fainted', 'double vision', 'stiff neck'
        ]
        
        has_emergency = [s for s in symptom_names if s in emergency_keywords]
        
        # If model is loaded, attempt TensorFlow inference
        if self.model_loaded and self.model is not None:
            try:
                features = self._prepare_features(symptom_names, patient_data)
                predictions = self.model.predict(features, verbose=0)[0]
                # Outputs probability for [low, medium, high, critical]
                classes = ['low', 'medium', 'high', 'critical']
                predicted_class_idx = int(np.argmax(predictions))
                predicted_level = classes[predicted_class_idx]
                score = float(predictions[predicted_class_idx])
                
                # Force critical if emergency symptom is detected
                if has_emergency:
                    predicted_level = 'critical'
                    score = 1.0
                    
                factors, recommendations = self._generate_factors_and_recs(predicted_level, symptom_names, patient_data, has_emergency)
                return {
                    'level': predicted_level,
                    'score': round(score, 2),
                    'factors': factors,
                    'recommendations': recommendations
                }
            except Exception as e:
                print(f"Error during risk model inference: {e}. Falling back to rule-based.")
                
        # Rule-based fallback
        return self._rule_based_risk(symptom_names, patient_data, has_emergency)

    def _prepare_features(self, symptom_names: list, patient_data: dict) -> np.ndarray:
        age = patient_data.get('age', 30)
        gender = patient_data.get('gender', 'unknown').lower()
        
        # Normalize age
        norm_age = age / 100.0
        
        # Encode gender
        gender_code = 0.5
        if gender == 'male':
            gender_code = 1.0
        elif gender == 'female':
            gender_code = 0.0
            
        # Create symptom vector
        symptom_vec = []
        for s in self.symptoms:
            s_name = s['name']
            symptom_vec.append(1.0 if s_name in symptom_names else 0.0)
            
        features = [norm_age, gender_code] + symptom_vec
        return np.array([features], dtype=np.float32)

    def _rule_based_risk(self, symptom_names: list, patient_data: dict, has_emergency: list) -> dict:
        score = 0.0
        factors = []
        
        # Evaluate severity of symptoms
        for s_name in symptom_names:
            # Find in symptoms list
            severity = 'mild'
            for s in self.symptoms:
                if s['name'] == s_name:
                    severity = s['severity']
                    break
            
            if severity == 'severe':
                score += 0.35
                factors.append(f"Severe symptom: {s_name}")
            elif severity == 'moderate':
                score += 0.20
                factors.append(f"Moderate symptom: {s_name}")
            else:
                score += 0.10
                
        # Demographic modifiers
        age = patient_data.get('age', 30)
        if age > 60:
            score += 0.15
            factors.append("Age over 60 years")
        elif age < 5:
            score += 0.15
            factors.append("Age under 5 years")
            
        # Chronic conditions modifier
        chronic = patient_data.get('chronic_conditions', [])
        if chronic:
            score += len(chronic) * 0.10
            factors.append(f"Chronic condition(s): {', '.join(chronic)}")
            
        # Classify risk level
        level = 'low'
        if score >= 0.70:
            level = 'high'
        elif score >= 0.40:
            level = 'medium'
            
        # Force critical on emergency keywords
        if has_emergency:
            level = 'critical'
            score = 1.0
            for es in has_emergency:
                factors.append(f"Emergency symptom: {es}")
                
        factors, recommendations = self._generate_factors_and_recs(level, symptom_names, patient_data, has_emergency)
        
        return {
            'level': level,
            'score': round(min(score, 1.0), 2),
            'factors': factors,
            'recommendations': recommendations
        }

    def _generate_factors_and_recs(self, level: str, symptom_names: list, patient_data: dict, has_emergency: list) -> tuple:
        factors = []
        
        # Populate explanation factors
        if has_emergency:
            for es in has_emergency:
                factors.append(f"Emergency symptom detected: '{es}'")
        else:
            severe_count = 0
            moderate_count = 0
            for s_name in symptom_names:
                for s in self.symptoms:
                    if s['name'] == s_name:
                        if s['severity'] == 'severe':
                            severe_count += 1
                        elif s['severity'] == 'moderate':
                            moderate_count += 1
            if severe_count > 0:
                factors.append(f"{severe_count} severe symptom(s) reported")
            if moderate_count > 0:
                factors.append(f"{moderate_count} moderate symptom(s) reported")
                
        age = patient_data.get('age', 30)
        if age > 60:
            factors.append("Vulnerable patient group (Age > 60)")
        elif age < 5:
            factors.append("Pediatric patient group (Age < 5)")
            
        chronic = patient_data.get('chronic_conditions', [])
        if chronic:
            factors.append(f"Underlying conditions: {', '.join(chronic)}")
            
        if not factors:
            factors.append("Mild symptoms reported")

        # Generate recommendations
        if level == 'critical':
            recs = "Go to the nearest emergency room (ER) immediately or call emergency services. Do not wait."
        elif level == 'high':
            recs = "We strongly recommend booking an appointment with a specialist today. Monitor vital signs closely."
        elif level == 'medium':
            recs = "Rest, keep hydrated, and monitor your symptoms. If symptoms persist for more than 48 hours or worsen, please consult a physician."
        else:
            recs = "Maintain hydration and rest. These symptoms appear mild, but consult a doctor if they do not improve within a few days."
            
        return factors, recs
