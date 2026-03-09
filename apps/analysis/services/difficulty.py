"""
Difficulty estimation service.
"""
import logging
from typing import Optional
import re

logger = logging.getLogger(__name__)


class DifficultyEstimator:
    """Estimates question difficulty level."""
    
    # Difficulty indicators
    EASY_INDICATORS = [
        'define', 'list', 'state', 'name', 'what is', 'give example',
        'identify', 'recall', 'basic', 'simple', 'elementary'
    ]
    
    MEDIUM_INDICATORS = [
        'explain', 'describe', 'compare', 'contrast', 'discuss',
        'illustrate', 'classify', 'solve', 'calculate', 'apply',
        'demonstrate', 'interpret'
    ]
    
    HARD_INDICATORS = [
        'analyze', 'evaluate', 'design', 'create', 'synthesize',
        'justify', 'critique', 'prove', 'derive', 'optimize',
        'complex', 'advanced', 'challenging', 'develop', 'construct'
    ]
    
    CLASSIFY_PROMPT = """
Estimate the difficulty level of this academic question.
Consider factors like:
- Cognitive demand (recall vs analysis vs creation)
- Number of steps required
- Complexity of concepts involved
- Marks allocated (if mentioned)

Question: {question_text}
Marks: {marks}

Respond with ONLY one word: easy, medium, or hard.
"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def estimate(self, question_text: str, marks: Optional[int] = None) -> str:
        """
        Estimate question difficulty.
        
        Returns: 'easy', 'medium', or 'hard'
        """
        # Try LLM estimation if available
        if self.llm_client:
            try:
                return self._estimate_with_llm(question_text, marks)
            except Exception as e:
                logger.warning(f"LLM estimation failed, falling back to heuristics: {e}")
        
        return self._estimate_by_heuristics(question_text, marks)
    
    def _estimate_with_llm(self, question_text: str, marks: Optional[int]) -> str:
        """Estimate using LLM."""
        marks_str = str(marks) if marks else "Not specified"
        prompt = self.CLASSIFY_PROMPT.format(
            question_text=question_text[:500],
            marks=marks_str
        )
        response = self.llm_client.generate(prompt, max_tokens=10)
        response = response.strip().lower()
        
        if response in ['easy', 'medium', 'hard']:
            return response
        
        return self._estimate_by_heuristics(question_text, marks)
    
    def _estimate_by_heuristics(self, question_text: str, marks: Optional[int]) -> str:
        """Estimate using heuristic rules."""
        question_lower = question_text.lower()
        
        # Count indicators
        easy_score = sum(1 for ind in self.EASY_INDICATORS if ind in question_lower)
        medium_score = sum(1 for ind in self.MEDIUM_INDICATORS if ind in question_lower)
        hard_score = sum(1 for ind in self.HARD_INDICATORS if ind in question_lower)
        
        # Consider marks if available
        if marks:
            if marks <= 2:
                easy_score += 2
            elif marks <= 5:
                medium_score += 2
            else:
                hard_score += 2
        
        # Consider question length (longer questions often more complex)
        word_count = len(question_text.split())
        if word_count < 20:
            easy_score += 1
        elif word_count > 50:
            hard_score += 1
        
        # Check for sub-parts (a, b, c)
        if re.search(r'\([a-z]\)', question_text) or re.search(r'[ivx]+\)', question_text):
            medium_score += 1
        
        # Determine difficulty
        scores = {'easy': easy_score, 'medium': medium_score, 'hard': hard_score}
        return max(scores, key=scores.get)
