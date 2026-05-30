class RiskEngine:
    def analyze(self, symptoms):
        high_risk = [
            "chest pain",
            "breathing difficulty"
        ]
        medium_risk = [
            "fever",
            "vomiting",
            "headache"
        ]
        score = 0
        for symptom in symptoms:
            if symptom in high_risk:
                score += 5
            elif symptom in medium_risk:
                score += 2

        if score >= 5:
            return "High"
        elif score >= 3:
            return "Medium"
        return "Low"
