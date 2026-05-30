import os
import csv
import shutil
import pandas as pd
import numpy as np
from django.utils import timezone

class DatasetManager:
    def __init__(self, dataset_dir=None):
        if not dataset_dir:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dataset_dir = os.path.join(current_dir, 'datasets')
            
        self.dataset_dir = dataset_dir
        os.makedirs(self.dataset_dir, exist_ok=True)
        
    def load_dataset(self, name: str) -> pd.DataFrame:
        """
        Load a dataset CSV file as a Pandas DataFrame.
        """
        csv_path = os.path.join(self.dataset_dir, f"{name}.csv")
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Dataset {name}.csv not found at {csv_path}")
        return pd.read_csv(csv_path)

    def save_dataset(self, name: str, df: pd.DataFrame):
        """
        Save a Pandas DataFrame to a CSV dataset file.
        """
        csv_path = os.path.join(self.dataset_dir, f"{name}.csv")
        df.to_csv(csv_path, index=False, encoding='utf-8')

    def backup_dataset(self, name: str) -> str:
        """
        Create a timestamped backup of the specified dataset.
        """
        csv_path = os.path.join(self.dataset_dir, f"{name}.csv")
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Cannot backup non-existent dataset: {name}.csv")
            
        backup_dir = os.path.join(self.dataset_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f"{name}_backup_{timestamp}.csv")
        shutil.copy2(csv_path, backup_path)
        return backup_path

    def validate_dataset(self, name: str) -> list:
        """
        Validate dataset schemas and identify missing columns, nulls, or invalid data.
        """
        errors = []
        try:
            df = self.load_dataset(name)
        except Exception as e:
            return [f"Failed to load dataset: {e}"]

        required_columns = {
            'symptoms': ['symptom_id', 'symptom_name', 'category', 'severity', 'body_part'],
            'diseases': ['disease_id', 'disease_name', 'symptoms', 'department', 'severity'],
            'medicines': ['medicine_id', 'medicine_name', 'disease', 'dosage'],
            'conversations': ['intent', 'pattern', 'response', 'language', 'category'],
            'telugu': ['english', 'telugu', 'tenglish', 'category'],
            'english': ['phrase', 'standard', 'category']
        }

        if name in required_columns:
            cols = required_columns[name]
            missing_cols = [c for c in cols if c not in df.columns]
            if missing_cols:
                errors.append(f"Missing required columns: {', '.join(missing_cols)}")
                
            # Check for critical nulls
            if not missing_cols:
                critical_cols = {
                    'symptoms': ['symptom_name', 'severity'],
                    'diseases': ['disease_name', 'symptoms'],
                    'conversations': ['pattern', 'response'],
                    'telugu': ['english', 'telugu'],
                    'english': ['phrase', 'standard']
                }
                if name in critical_cols:
                    for col in critical_cols[name]:
                        null_count = df[col].isnull().sum()
                        if null_count > 0:
                            errors.append(f"Column '{col}' has {null_count} null/missing values.")
        else:
            errors.append(f"Unknown dataset name for validation validation: {name}")

        return errors

    def get_statistics(self, name: str) -> dict:
        """
        Get row count, column details, and summary stats for a dataset.
        """
        try:
            df = self.load_dataset(name)
            stats = {
                'row_count': len(df),
                'columns': list(df.columns),
                'null_counts': df.isnull().sum().to_dict(),
            }
            # Add category distributions if column exists
            for col in ['category', 'severity', 'department', 'language', 'intent']:
                if col in df.columns:
                    stats[f'{col}_distribution'] = df[col].value_counts().to_dict()
            return stats
        except Exception as e:
            return {'error': str(e)}

    def merge_new_data(self, name: str, new_rows_list: list):
        """
        Append and merge new data entries into an existing dataset with deduplication.
        """
        if not new_rows_list:
            return
            
        self.backup_dataset(name)
        df_existing = self.load_dataset(name)
        df_new = pd.DataFrame(new_rows_list)
        
        # Merge and drop duplicates
        df_merged = pd.concat([df_existing, df_new], ignore_index=True)
        
        # Deduplicate based on unique identifiers
        dedup_keys = {
            'symptoms': ['symptom_name'],
            'diseases': ['disease_name'],
            'conversations': ['pattern', 'response'],
            'telugu': ['english', 'telugu'],
            'english': ['phrase', 'standard']
        }
        
        subset = dedup_keys.get(name)
        if subset:
            # Keep the newest records (the ones at the end)
            df_merged.drop_duplicates(subset=subset, keep='last', inplace=True)
            
        self.save_dataset(name, df_merged)
