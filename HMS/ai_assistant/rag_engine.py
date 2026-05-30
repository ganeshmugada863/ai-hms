import os
import re
import math

class RAGEngine:
    def __init__(self, kb_dir=None):
        if kb_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            kb_dir = os.path.join(current_dir, 'knowledge_base')
        self.kb_dir = kb_dir
        self.chunks = []
        self.load_knowledge_base()

    def _clean_text(self, text):
        # Lowercase, remove non-alphanumeric (keep spaces), split
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', '', text)
        return text.split()

    def load_knowledge_base(self):
        self.chunks = []
        if not os.path.exists(self.kb_dir):
            return
        
        stop_words = {'a', 'an', 'the', 'is', 'of', 'and', 'in', 'to', 'for', 'with', 'my', 'your', 'i', 'you', 'me', 'what', 'how', 'are', 'can', 'do', 'at', 'on', 'or', 'about'}
        
        # Scan all .txt files
        for filename in os.listdir(self.kb_dir):
            if filename.endswith('.txt'):
                filepath = os.path.join(self.kb_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # Split by double newline or multiple newlines
                    paragraphs = re.split(r'\n\s*\n', content)
                    for para in paragraphs:
                        para = para.strip()
                        if para:
                            words = self._clean_text(para)
                            filtered_words = [w for w in words if w not in stop_words]
                            if filtered_words:
                                self.chunks.append({
                                    'text': para,
                                    'words': words,
                                    'filtered_words': set(filtered_words),
                                    'source': filename
                                })
                except Exception as e:
                    print(f"Error loading {filename}: {e}")

    def search_kb(self, query: str, threshold: float = 0.05) -> str:
        if not query or not self.chunks:
            return None
            
        stop_words = {'a', 'an', 'the', 'is', 'of', 'and', 'in', 'to', 'for', 'with', 'my', 'your', 'i', 'you', 'me', 'what', 'how', 'are', 'can', 'do', 'at', 'on', 'or', 'about'}
        query_words = self._clean_text(query)
        filtered_query = [w for w in query_words if w not in stop_words]
        
        if not filtered_query:
            # Fallback to all words if query consists only of stopwords
            filtered_query = query_words
            
        if not filtered_query:
            return None
            
        best_chunk = None
        best_score = -1.0
        
        # Calculate DF for IDF
        total_chunks = len(self.chunks)
        df = {}
        for chunk in self.chunks:
            for w in chunk['filtered_words']:
                df[w] = df.get(w, 0) + 1
                
        # Search
        for chunk in self.chunks:
            score = 0.0
            overlap_words = chunk['filtered_words'].intersection(set(filtered_query))
            if not overlap_words:
                continue
                
            for word in overlap_words:
                # TF in chunk
                tf = chunk['words'].count(word) / len(chunk['words'])
                # IDF
                doc_freq = df.get(word, 0)
                idf = math.log((1 + total_chunks) / (1 + doc_freq)) + 1
                score += tf * idf
                
            # Normalize by query length and add query overlap ratio boost
            overlap_ratio = len(overlap_words) / len(set(filtered_query))
            final_score = score * overlap_ratio
            
            if final_score > best_score:
                best_score = final_score
                best_chunk = chunk
                
        if best_chunk and best_score >= threshold:
            return best_chunk['text']
            
        return None
