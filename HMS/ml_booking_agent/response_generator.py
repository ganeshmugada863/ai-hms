def generate(symptoms, risk):
    questions = []
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

    return {
      "Symptoms": symptoms,
      "Risk": risk,
      "Questions": questions if questions else ["More symptoms?", "How long?"]
    }
