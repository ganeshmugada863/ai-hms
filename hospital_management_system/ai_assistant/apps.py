import logging
from django.apps import AppConfig

logger = logging.getLogger('ai_assistant')

class AIAssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_assistant'

    chatbot_instance = None

    def ready(self):
        # Lazy initialization is deferred to prevent startup delays and issues during migrations/checkups
        logger.info("AI Assistant app config loaded. Models will lazy-load on first interaction.")

    @classmethod
    def get_chatbot(cls):
        if cls.chatbot_instance is None:
            logger.info("Initializing AI ChatBot singleton instance...")
            try:
                from ai_assistant.train_bot import ChatBot
                cls.chatbot_instance = ChatBot()
            except Exception as e:
                logger.error(f"Error initializing ChatBot singleton: {e}")
                # Fallback to local import without models if necessary, or let it propagate
                raise e
        return cls.chatbot_instance

    @classmethod
    def reload_engines(cls):
        logger.info("Hot-reloading AI Engines...")
        try:
            from ai_assistant.train_bot import ChatBot
            cls.chatbot_instance = ChatBot()
            logger.info("AI Engines successfully hot-reloaded.")
        except Exception as e:
            logger.error(f"Failed to reload AI engines: {e}")

