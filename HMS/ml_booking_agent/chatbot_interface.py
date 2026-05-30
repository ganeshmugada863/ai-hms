# chatbot_interface.py

class HealthcareBot:
    def __init__(self):
        self.context = {}

    def get_response(self, user_input, analysis_results, llm_provider="neural_network", patient_history=None):
        """
        Generates a human-like response based on ML analysis or routes to an Advanced LLM.
        """
        is_chat = analysis_results.get('is_chat', False)
        ml_context = analysis_results.get('ml_context', '')
        
        # Route to the Massive Neural Network Engine
        try:
            from .llm_service import generate_llm_response
            return generate_llm_response("neural_network", user_input, analysis_results, is_chat, patient_history)
        except Exception as e:
            return f"⚠️ Error initializing LLM service: {str(e)}"
                
        # Default Hardcoded Logic (Fallback)
        if is_chat:
            import random
            greetings = [
                "Hello! How can I assist you with your health today? Please describe any symptoms you're experiencing.",
                "Hi there! I am your AI Health Assistant. Tell me how you're feeling.",
                "Greetings! If you have any medical concerns, just type them here and I'll analyze them for you."
            ]
            return random.choice(greetings)

        dept = analysis_results.get('suggested_department')
        severity = analysis_results.get('severity')
        solution = analysis_results.get('recommended_solution', 'Please consult a doctor.')
        disease = analysis_results.get('disease_prediction', 'an unknown condition')
        
        # Build context-aware response based on our ML zero-shot output
        response = f"Based on my analysis, this may be related to {disease}. {solution}"
        
        if severity == "High":
            return response + f" I strongly recommend seeing a specialist in {dept} immediately."
        elif severity == "Medium":
            return response + f" It's best to consult with our {dept} department soon to prevent it from worsening. Would you like to see the available doctors?"
        else:
            return response + f" It looks like a mild condition currently, but it's safe to consult with our {dept} department. Would you like to see available doctors?"

    def get_welcome_message(self):
        return ""