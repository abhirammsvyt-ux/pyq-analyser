"""
Bloom's Taxonomy classification service.
"""
import logging
from typing import Optional
import re

logger = logging.getLogger(__name__)


class BloomClassifier:
    """Classifies questions according to Bloom's Taxonomy."""
    
    # Keywords associated with each Bloom's level
    BLOOM_KEYWORDS = {
        'remember': [
            'define', 'list', 'state', 'name', 'identify', 'recall',
            'recognize', 'describe', 'label', 'match', 'select', 'what is',
            'who', 'when', 'where', 'how many', 'enumerate'
        ],
        'understand': [
            'explain', 'summarize', 'interpret', 'classify', 'compare',
            'contrast', 'discuss', 'distinguish', 'illustrate', 'translate',
            'paraphrase', 'give example', 'differentiate', 'infer'
        ],
        'apply': [
            'apply', 'demonstrate', 'calculate', 'solve', 'use', 'compute',
            'implement', 'execute', 'perform', 'construct', 'show', 'produce',
            'operate', 'determine', 'find', 'draw'
        ],
        'analyze': [
            'analyze', 'examine', 'investigate', 'compare and contrast',
            'categorize', 'deduce', 'differentiate', 'distinguish', 'outline',
            'break down', 'relate', 'organize', 'attribute', 'deconstruct'
        ],
        'evaluate': [
            'evaluate', 'judge', 'assess', 'justify', 'critique', 'defend',
            'argue', 'support', 'appraise', 'recommend', 'prioritize', 'rate',
            'decide', 'verify', 'validate', 'criticize'
        ],
        'create': [
            'create', 'design', 'develop', 'formulate', 'propose', 'construct',
            'invent', 'compose', 'generate', 'plan', 'produce', 'devise',
            'synthesize', 'integrate', 'modify', 'write a program', 'build'
        ]
    }
    
    # LLM prompt for more accurate classification
    CLASSIFY_PROMPT = """
Classify the following question according to Bloom's Taxonomy cognitive levels:
1. Remember - Recall facts and basic concepts
2. Understand - Explain ideas or concepts
3. Apply - Use information in new situations
4. Analyze - Draw connections among ideas
5. Evaluate - Justify a decision or course of action
6. Create - Produce new or original work

Question: {question_text}

Respond with ONLY one word: remember, understand, apply, analyze, evaluate, or create.
"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def classify(self, question_text: str) -> str:
        """
        Classify a question using Bloom's Taxonomy.
        
        Returns one of: remember, understand, apply, analyze, evaluate, create
        """
        # Try LLM classification first if available
        if self.llm_client:
            try:
                return self._classify_with_llm(question_text)
            except Exception as e:
                logger.warning(f"LLM classification failed, falling back to keywords: {e}")
        
        # Fallback to keyword-based classification
        return self._classify_by_keywords(question_text)
    
    def _classify_with_llm(self, question_text: str) -> str:
        """Classify using LLM."""
        prompt = self.CLASSIFY_PROMPT.format(question_text=question_text[:500])
        response = self.llm_client.generate(prompt, max_tokens=10)
        response = response.strip().lower()
        
        if response in self.BLOOM_KEYWORDS:
            return response
        
        # If LLM gives unexpected response, fall back to keywords
        return self._classify_by_keywords(question_text)
    
    def _classify_by_keywords(self, question_text: str) -> str:
        """Classify using keyword matching."""
        question_lower = question_text.lower()
        
        # Score each level
        scores = {level: 0 for level in self.BLOOM_KEYWORDS}
        
        for level, keywords in self.BLOOM_KEYWORDS.items():
            for keyword in keywords:
                # Check if keyword appears as a whole word
                pattern = r'\b' + re.escape(keyword) + r'\b'
                matches = len(re.findall(pattern, question_lower))
                scores[level] += matches * (len(self.BLOOM_KEYWORDS) - list(self.BLOOM_KEYWORDS.keys()).index(level))
        
        # Return the level with highest score
        best_level = max(scores, key=scores.get)
        
        # If no keywords matched, default to 'understand'
        if scores[best_level] == 0:
            return 'understand'
        
        return best_level
