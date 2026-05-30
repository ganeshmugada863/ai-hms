from django.core.management.base import BaseCommand
from ai_assistant.model_trainer import ModelTrainer

class Command(BaseCommand):
    help = 'Train all local AI Assistant TensorFlow models (symptom, disease, risk)'

    def handle(self, *args, **options):
        self.stdout.write("Initializing model training pipeline...")
        try:
            trainer = ModelTrainer()
            metrics = trainer.train_all()
            
            if 'error' in metrics and len(metrics) == 1:
                self.stdout.write(self.style.ERROR(f"[-] Fatal error during training: {metrics['error']}"))
                return
                
            for model_type, metric in metrics.items():
                if isinstance(metric, dict) and 'error' in metric:
                    self.stdout.write(self.style.ERROR(f"[-] Error training {model_type}: {metric['error']}"))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"[+] Successfully trained {model_type} model!\n"
                        f"    - Accuracy: {metric.get('accuracy', 0.0):.2%}\n"
                        f"    - Training Samples: {metric.get('samples', 0)}\n"
                        f"    - Metric Info: {', '.join([f'{k}: {v}' for k, v in metric.items() if k not in ['accuracy', 'samples']])}"
                    ))
            self.stdout.write(self.style.SUCCESS("All models trained and registry updated successfully!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Fatal error during model training: {e}"))
