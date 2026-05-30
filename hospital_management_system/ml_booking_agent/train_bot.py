class ChatbotResponseEngine:

    def extract_symptoms(self, text):
        symptoms_db = [
            "headache",
            "fever",
            "cough",
            "vomiting",
            "chest pain",
            "dizziness",
            "breathing difficulty"
        ]

        found=[]
        text=text.lower()

        for symptom in symptoms_db:
            if symptom in text:
                found.append(symptom)

        return found


    def ask_missing_info(self,symptoms):
        questions=[]

        if "headache" in symptoms:
            questions.extend([
                "Do you have fever?",
                "Is the pain severe or mild?",
                "Do you have dizziness?"
            ])

        if "fever" in symptoms:
            questions.extend([
                "What is your temperature?",
                "Do you have cough?",
                "How many days?"
            ])

        if "chest pain" in symptoms:
            questions.extend([
                "Do you have breathing difficulty?",
                "Is pain spreading to arm?",
                "Do you have sweating?"
            ])

        return questions


    def risk_analysis(self,symptoms):
        high_risk = [
            "chest pain",
            "breathing difficulty"
        ]

        medium_risk = [
            "fever",
            "vomiting",
            "headache"
        ]

        score=0

        for symptom in symptoms:
            if symptom in high_risk:
                score+=5
            elif symptom in medium_risk:
                score+=2

        if score>=5:
            return "High"
        elif score>=3:
            return "Medium"

        return "Low"


    def generate(self,user_question):
        symptoms=self.extract_symptoms(
            user_question
        )

        missing_questions=self.ask_missing_info(
            symptoms
        )

        risk=self.risk_analysis(
            symptoms
        )

        response = {
            "Detected_Symptoms": symptoms,
            "Need_More_Info": missing_questions,
            "Risk_Level": risk
        }

        return response


if __name__ == '__main__':
    bot=ChatbotResponseEngine()

    result=bot.generate(
        "I have headache from 2 days"
    )

    print(result)
