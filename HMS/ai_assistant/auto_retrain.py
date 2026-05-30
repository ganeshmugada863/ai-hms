import os
import json
import pandas as pd
import numpy as np
from django.utils import timezone
from django.conf import settings

from ai_assistant.dataset_manager import DatasetManager
from ai_assistant.model_trainer import ModelTrainer

class AutoRetrainer:
    def __init__(self):
        self.dm = DatasetManager()
        self.trainer = ModelTrainer()
        
    def check_and_retrain(self, force=False) -> bool:
        """
        Check if pending items in RetrainQueue exceed the configured threshold, 
        and trigger retrain pipeline.
        """
        from ai_assistant.models import RetrainQueue
        
        pending_items = RetrainQueue.objects.filter(status='pending')
        count = pending_items.count()
        
        # Get threshold from Django settings configuration
        ai_config = getattr(settings, 'AI_ASSISTANT', {})
        threshold = ai_config.get('RETRAIN_THRESHOLD', 50)
        
        if count >= threshold or (force and count > 0):
            print(f"Starting auto-retraining pipeline for {count} pending sessions...")
            
            # Mark as processing
            pending_items.update(status='processing')
            
            try:
                # 1. Collect and clean new data
                new_symptoms, new_conversations = self.collect_new_data(pending_items)
                
                # 2. Merge into CSV datasets
                if new_symptoms:
                    self.dm.merge_new_data('symptoms', new_symptoms)
                if new_conversations:
                    self.dm.merge_new_data('conversations', new_conversations)
                    
                # 3. Train models
                metrics = self.trainer.train_all()
                print("Model retraining finished with metrics:", metrics)
                
                # 4. Run unsupervised clustering on unrecognized/unknown messages
                self.discover_new_patterns()
                
                # 5. Hot-reload models in Django App Config
                self.reload_models()
                
                # Mark queue items as completed
                pending_items.update(
                    status='completed', 
                    processed_at=timezone.now()
                )
                return True
                
            except Exception as e:
                error_msg = f"Retraining failed: {str(e)}"
                print(error_msg)
                pending_items.update(
                    status='failed',
                    error_message=error_msg,
                    processed_at=timezone.now()
                )
                raise e
        else:
            print(f"Retrain check: {count} pending sessions. Threshold is {threshold}. Skipping.")
            return False

    def collect_new_data(self, queue_items) -> tuple:
        """
        Collect symptoms and conversation lines from the processed queue sessions.
        """
        new_symptoms = []
        new_conversations = []
        
        for item in queue_items:
            session = item.session
            if not session:
                continue
                
            # Collect messages
            messages = session.messages.all()
            for msg in messages:
                if msg.role == 'user':
                    # Check if symptoms were verified/extracted
                    # For conversations.csv, we can add user query + bot response patterns
                    bot_replies = session.messages.filter(role='bot', timestamp__gt=msg.timestamp)
                    if bot_replies.exists():
                        bot_reply = bot_replies.first()
                        new_conversations.append({
                            'intent': 'symptom_report' if session.extracted_symptoms else 'greeting',
                            'pattern': msg.content.strip().lower(),
                            'response': bot_reply.content.strip(),
                            'response_te': bot_reply.content.strip() if session.language == 'te' else '',
                            'language': session.language,
                            'category': 'symptom' if session.extracted_symptoms else 'general'
                        })
                        
        return new_symptoms, new_conversations

    def discover_new_patterns(self):
        """
        Perform unsupervised KMeans clustering on user messages where no symptoms were
        extracted, to discover new clinical terms or symptom descriptions.
        """
        from ai_assistant.models import ChatMessage
        
        # Get all user messages with empty extracted symptoms
        unrecognized_msgs = ChatMessage.objects.filter(
            role='user', 
            symptom_entries__isnull=True
        ).order_by('-timestamp')[:200]
        
        texts = [m.content.strip() for m in unrecognized_msgs if len(m.content.strip()) > 5]
        
        if len(texts) < 10:
            return # Too few samples to cluster
            
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.cluster import KMeans
            
            # Vectorize texts
            vectorizer = TfidfVectorizer(max_features=500, stop_words='english')
            X = vectorizer.fit_transform(texts)
            
            # Determine number of clusters
            num_clusters = min(5, len(texts) // 3)
            if num_clusters < 2:
                return
                
            kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init='auto')
            kmeans.fit(X)
            
            # Identify keywords per cluster
            order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
            terms = vectorizer.get_feature_names_out()
            
            clusters = {}
            for i in range(num_clusters):
                cluster_terms = [terms[ind] for ind in order_centroids[i, :6]]
                # Find representative text samples
                cluster_samples = []
                for idx, label in enumerate(kmeans.labels_):
                    if label == i:
                        cluster_samples.append(texts[idx])
                        if len(cluster_samples) >= 3:
                            break
                            
                clusters[f"cluster_{i}"] = {
                    'keywords': cluster_terms,
                    'samples': cluster_samples
                }
                
            # Write findings to datasets folder for admin view
            output_path = os.path.join(self.dm.dataset_dir, 'discovered_patterns.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(clusters, f, indent=4)
                
            print(f"Unsupervised clustering discovered {num_clusters} new pattern groups. Saved to discovered_patterns.json.")
            
        except Exception as e:
            print(f"Warning: Unsupervised clustering failed: {e}")

    def reload_models(self):
        """
        Instruct the running Django app to reload models from files.
        """
        try:
            from django.apps import apps
            app_config = apps.get_app_config('ai_assistant')
            # Trigger reload hook on the AppConfig
            if hasattr(app_config, 'reload_engines'):
                app_config.reload_engines()
                print("AI Engines successfully hot-reloaded in Django runtime.")
        except Exception as e:
            print(f"Warning: Failed to hot-reload models: {e}")
