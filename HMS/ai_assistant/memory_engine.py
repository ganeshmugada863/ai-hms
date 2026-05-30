import os
import json
import re
from django.utils import timezone
from django.db.models import Q
from django.core.serializers.json import DjangoJSONEncoder

class MemoryEngine:
    def __init__(self):
        # Lazy imports are not strictly needed here since we run inside Django context,
        # but importing dynamically inside methods helps avoid circular imports.
        pass

    def get_context(self, patient) -> dict:
        """
        Aggregate all medical and conversational context for a patient.
        """
        from ai_assistant.models import PatientMemory
        
        # Demographics from patient profile
        context = {
            'patient_id': patient.id,
            'username': patient.user.username,
            'demographics': {
                'age': patient.age,
                'gender': patient.gender,
                'blood_group': patient.blood_group,
                'medical_history_text': patient.medical_history
            },
            'allergies': [],
            'chronic_conditions': [],
            'current_medications': [],
            'past_diagnoses': [],
            'family_history': [],
            'lifestyle': {},
            'past_symptoms': []
        }

        # 1. Fetch memories from PatientMemory
        memories = PatientMemory.objects.filter(patient=patient)
        for mem in memories:
            category = mem.category
            key = mem.key
            value = mem.value
            
            item = {'key': key, 'value': value, 'source': mem.source, 'last_updated': mem.last_updated}
            
            if category == 'allergy':
                context['allergies'].append(item)
            elif category == 'chronic':
                context['chronic_conditions'].append(item)
            elif category == 'medication':
                context['current_medications'].append(item)
            elif category == 'past_diagnosis':
                context['past_diagnoses'].append(item)
            elif category == 'family_history':
                context['family_history'].append(item)
            elif category == 'lifestyle':
                context['lifestyle'][key] = value

        # 2. If PatientMemory is empty, try to bootstrap it from historical Django models
        if not memories.exists():
            self._bootstrap_memory(patient, context)

        # 3. Add past symptoms from ChatSessions
        context['past_symptoms'] = self.get_past_symptoms(patient)

        # 4. Fetch recent prescriptions not yet in memory
        recent_prescriptions = self.get_medications(patient)
        for rx in recent_prescriptions:
            # Check if already present in medications memory
            exists = any(m['key'].lower() == rx['name'].lower() for m in context['current_medications'])
            if not exists:
                context['current_medications'].append({
                    'key': rx['name'],
                    'value': {'dosage': rx['dosage'], 'date': rx['date']},
                    'source': 'prescription',
                    'last_updated': rx['date']
                })
                
        # 5. Fetch recent diagnoses from prescriptions / consults
        recent_diagnoses = self.get_past_diagnoses(patient)
        for dx in recent_diagnoses:
            exists = any(d['key'].lower() == dx['name'].lower() for d in context['past_diagnoses'])
            if not exists:
                context['past_diagnoses'].append({
                    'key': dx['name'],
                    'value': {'date': dx['date'], 'type': dx['type']},
                    'source': dx['type'],
                    'last_updated': dx['date']
                })

        return context

    def store(self, patient, key: str, value: dict, category: str, source='chat') -> tuple:
        """
        Store or update a memory entry for a patient.
        """
        from ai_assistant.models import PatientMemory
        
        # Clean inputs
        key = key.strip()
        category = category.strip().lower()
        
        # Valid categories
        valid_categories = ['allergy', 'chronic', 'medication', 'family_history', 'lifestyle', 'past_diagnosis', 'other']
        if category not in valid_categories:
            category = 'other'

        memory, created = PatientMemory.objects.update_or_create(
            patient=patient,
            key=key,
            defaults={
                'value': value,
                'category': category,
                'source': source
            }
        )
        return memory, created

    def get_past_symptoms(self, patient) -> list:
        """
        Retrieve past symptoms extracted from the patient's AI ChatSessions.
        """
        from ai_assistant.models import ChatSession
        
        symptoms_history = []
        sessions = ChatSession.objects.filter(patient=patient).order_by('-started_at')
        
        for sess in sessions:
            if sess.extracted_symptoms:
                for sym in sess.extracted_symptoms:
                    # sym is expected to be a dict or string
                    sym_name = sym if isinstance(sym, str) else sym.get('name', '')
                    if sym_name and sym_name not in symptoms_history:
                        symptoms_history.append(sym_name)
                        
        return symptoms_history

    def get_past_diagnoses(self, patient) -> list:
        """
        Get past diagnoses from prescriptions, medical records, and AI predictions.
        """
        from prescriptions.models import Prescription
        from ai_assistant.models import DiseasePrediction
        
        diagnoses = []
        
        # 1. From prescriptions
        rx_list = Prescription.objects.filter(patient=patient).order_by('-prescribed_date')
        for rx in rx_list:
            if rx.diagnosis:
                diagnoses.append({
                    'name': rx.diagnosis.strip(),
                    'date': rx.prescribed_date,
                    'type': 'prescription'
                })
                
        # 2. From AI disease predictions
        ai_preds = DiseasePrediction.objects.filter(session__patient=patient).order_by('-predicted_at')
        for pred in ai_preds:
            # Only add confident predictions (> 50%)
            if pred.confidence >= 0.50:
                diagnoses.append({
                    'name': pred.disease_name.strip(),
                    'date': pred.predicted_at,
                    'type': 'ai_prediction'
                })
                
        return diagnoses

    def get_medications(self, patient) -> list:
        """
        Get current and past medications from prescriptions.
        """
        from prescriptions.models import Prescription
        
        medications = []
        rx_list = Prescription.objects.filter(patient=patient).order_by('-prescribed_date')
        
        for rx in rx_list:
            if rx.medicines:
                # Split medicines (could be newline or comma separated)
                parts = re.split(r'[\n,;]', rx.medicines)
                for part in parts:
                    name = part.strip()
                    if name:
                        medications.append({
                            'name': name,
                            'dosage': rx.dosage_instructions,
                            'date': rx.prescribed_date
                        })
                        
        return medications

    def get_allergies(self, patient) -> list:
        """
        Retrieve list of allergies from memory.
        """
        from ai_assistant.models import PatientMemory
        
        allergies = []
        memories = PatientMemory.objects.filter(patient=patient, category='allergy')
        for mem in memories:
            allergies.append(mem.key)
            
        return allergies

    def export_to_json(self, patient) -> dict:
        """
        Export patient history to a local JSON file in memory/ folder and return context.
        """
        context = self.get_context(patient)
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        memory_dir = os.path.join(current_dir, 'memory')
        
        # Ensure memory directory exists
        os.makedirs(memory_dir, exist_ok=True)
        
        file_path = os.path.join(memory_dir, f"{patient.id}_history.json")
        # Also maintain a general patient_history.json as a copy
        general_file_path = os.path.join(memory_dir, "patient_history.json")
        
        try:
            # Serialize dates properly using DjangoJSONEncoder
            json_data = json.dumps(context, cls=DjangoJSONEncoder, indent=4)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_data)
            with open(general_file_path, 'w', encoding='utf-8') as f:
                f.write(json_data)
        except Exception as e:
            print(f"Error exporting patient memory to JSON: {e}")
            
        return context

    def _bootstrap_memory(self, patient, context):
        """
        Helper method to parse baseline text medical_history and boot-up PatientMemory entries.
        """
        # Parse medical history text for conditions/allergies
        history_text = patient.medical_history
        if not history_text:
            return
            
        # Parse typical text like: "Asthma, Allergy to peanuts, Diabetes"
        elements = [item.strip() for item in re.split(r'[,;\n.]', history_text) if item.strip()]
        for elem in elements:
            elem_lower = elem.lower()
            if 'allergy to' in elem_lower or 'allergic to' in elem_lower:
                allergy_name = elem.replace('Allergy to', '').replace('allergy to', '').replace('allergic to', '').replace('Allergic to', '').strip()
                if allergy_name:
                    self.store(patient, allergy_name, {'details': 'Imported from medical history text'}, 'allergy', 'profile')
                    context['allergies'].append({
                        'key': allergy_name,
                        'value': {'details': 'Imported from medical history text'},
                        'source': 'profile',
                        'last_updated': timezone.now()
                    })
            elif 'diabetes' in elem_lower or 'asthma' in elem_lower or 'hypertension' in elem_lower or 'bp' in elem_lower or 'thyroid' in elem_lower or 'arthritis' in elem_lower:
                self.store(patient, elem, {'details': 'Imported from medical history text'}, 'chronic', 'profile')
                context['chronic_conditions'].append({
                    'key': elem,
                    'value': {'details': 'Imported from medical history text'},
                    'source': 'profile',
                    'last_updated': timezone.now()
                })
            else:
                # Add as general chronic or past diagnosis
                self.store(patient, elem, {'details': 'Imported from medical history text'}, 'past_diagnosis', 'profile')
                context['past_diagnoses'].append({
                    'key': elem,
                    'value': {'details': 'Imported from medical history text'},
                    'source': 'profile',
                    'last_updated': timezone.now()
                })
