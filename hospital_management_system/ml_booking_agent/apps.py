from django.apps import AppConfig


class MlBookingAgentConfig(AppConfig):
    name = 'ml_booking_agent'

    def ready(self):
        import ml_booking_agent.signals

