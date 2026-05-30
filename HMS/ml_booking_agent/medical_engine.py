class MedicalEngine:
    def extract_symptoms(self, text):
        symptoms = [
            "headache",
            "fever",
            "cough",
            "vomiting",
            "chest pain",
            "dizziness",
            "breathing difficulty"
        ]
        return [s for s in symptoms if s in text.lower()]
