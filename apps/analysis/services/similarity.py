"""
Duplicate detection service using cosine similarity.
"""
import logging
from typing import List, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)


class SimilarityService:
    """Detects duplicate questions using embedding similarity."""
    
    def __init__(self, threshold: float = 0.80):
        # 0.80 → same question; 0.65–0.79 can be treated as same topic by callers
        self.threshold = threshold
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            a = np.array(vec1)
            b = np.array(vec2)
            
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            return float(dot_product / (norm_a * norm_b))
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0
    
    def find_duplicates(
        self,
        question_id: str,
        question_embedding: List[float],
        existing_questions: List[Tuple[str, List[float]]]
    ) -> Optional[Tuple[str, float]]:
        """
        Find if a question is a duplicate of any existing questions.
        
        Args:
            question_id: ID of the question to check
            question_embedding: Embedding of the question
            existing_questions: List of (question_id, embedding) tuples
            
        Returns:
            (duplicate_id, similarity_score) or None
        """
        if not question_embedding:
            return None
        
        best_match = None
        best_score = 0.0
        
        for other_id, other_embedding in existing_questions:
            if other_id == question_id or not other_embedding:
                continue
            
            score = self.cosine_similarity(question_embedding, other_embedding)
            
            if score >= self.threshold and score > best_score:
                best_score = score
                best_match = other_id
        
        if best_match:
            return (best_match, best_score)
        return None
    
    def batch_find_duplicates(
        self,
        questions: List[Tuple[str, List[float]]]
    ) -> List[Tuple[str, str, float]]:
        """
        Find all duplicates within a set of questions.
        
        Returns:
            List of (question_id, duplicate_of_id, similarity_score)
        """
        duplicates = []
        
        for i, (q_id, q_emb) in enumerate(questions):
            if not q_emb:
                continue
            
            # Only check against questions that came before (to avoid double-counting)
            for j in range(i):
                other_id, other_emb = questions[j]
                if not other_emb:
                    continue
                
                score = self.cosine_similarity(q_emb, other_emb)
                
                if score >= self.threshold:
                    duplicates.append((q_id, other_id, score))
                    break  # One duplicate is enough
        
        return duplicates
