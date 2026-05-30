from django.core.management.base import BaseCommand
from ai_assistant.auto_retrain import AutoRetrainer

class Command(BaseCommand):
    help = 'Check RetrainQueue and run auto retraining if pending items reach the threshold'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Force training immediately, bypassing count threshold')

    def handle(self, *args, **options):
        self.stdout.write("Checking RetrainQueue for pending items...")
        try:
            ar = AutoRetrainer()
            force = options.get('force', False)
            triggered = ar.check_and_retrain(force=force)
            
            if triggered:
                self.stdout.write(self.style.SUCCESS("[+] Retrain execution completed successfully! Models updated."))
            else:
                self.stdout.write(self.style.WARNING("[!] Training threshold not met. No retrain triggered."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Fatal error during retraining queue execution: {e}"))
