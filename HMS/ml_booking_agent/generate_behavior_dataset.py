import json
import random
import os

greetings = [
    "Hi",
    "Hello",
    "Hey",
    "Good morning",
    "Hi AI",
    "నమస్కారం",
    "హలో",
    "నమస్తే",
    "శుభోదయం"
]

greeting_responses = [
    "Hello! Nenu meeku ela help cheyagalanu?",
    "Hi! Meeku em sahayam kavali?",
    "Hello! Mee roju ela undi?"
]

angry_inputs = [
    "Nuvvu useless",
    "Wrong answer ichav",
    "Naku nachaledu",
    "Nuvvu emi cheyyalevu",
    "నువ్వు useless",
    "తప్పు సమాధానం ఇచ్చావు",
    "నాకు నచ్చలేదు",
    "నువ్వు ఏమి చేయలేవు"
]

angry_responses = [
    "Mee frustration ardham avutundi. Problem details cheppandi.",
    "Sorry mee expectation match avvaledu. Inkoka sari try cheddam.",
    "Mee issue explain chesthe nenu help chestanu."
]

symptoms = [
    "fever",
    "headache",
    "cough",
    "vomiting",
    "chest pain",
    "జ్వరం",
    "తలనొప్పి",
    "దగ్గు",
    "వాంతులు",
    "గుండె నొప్పి"
]

followups = [
    "Ee symptoms eppati nundi unnayi?",
    "Temperature entha undi?",
    "Vere symptoms emaina unnaya?"
]

dataset=[]

for i in range(50000):

    category=random.choice([
        "greeting",
        "angry",
        "symptom"
    ])

    if category=="greeting":

        data={
            "instruction":"Behave professionally",
            "input":random.choice(greetings),
            "output":random.choice(
                greeting_responses
            ),
            "category": "greeting"
        }

    elif category=="angry":

        data={
            "instruction":"Stay calm and respectful",
            "input":random.choice(
                angry_inputs
            ),
            "output":random.choice(
                angry_responses
            ),
            "category": "angry"
        }

    else:

        symptom=random.choice(symptoms)
        if any('\u0c00' <= char <= '\u0c7f' for char in symptom):
            prompt = f"నాకు {symptom} ఉంది"
        else:
            prompt = f"Naku {symptom} undi"

        data={
            "instruction":"Ask follow-up questions",
            "input":prompt,
            "output":random.choice(
                followups
            ),
            "category": "symptom"
        }

    dataset.append(data)

base_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(base_dir, "behavior_dataset.json")

with open(
    json_path,
    "w",
    encoding="utf8"
) as f:

    json.dump(
        dataset,
        f,
        ensure_ascii=False,
        indent=2
    )

print(
"50000 dataset examples generated with Telugu script support"
)
