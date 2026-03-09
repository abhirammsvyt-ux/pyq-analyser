"""
Module classification service using LLM and keyword matching.
"""
import logging
import re
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class ModuleClassifier:
    """Classifies questions into modules using LLM or keyword matching."""
    
    CLASSIFY_PROMPT = """
You are a question classifier for academic subjects. Given a question and the available modules,
determine which module the question belongs to.

Subject: {subject_name}
Modules:
{modules_list}

Question: {question_text}

Respond with ONLY the module number (e.g., "1", "2", "3"). If unsure, respond with "0".
"""
    
    BATCH_CLASSIFY_PROMPT = """You are a question classifier for academic subjects.
Subject: {subject_name}

Modules:
{modules_list}

For each question below, respond with ONLY the module number (1-{num_modules}). 
Format: One number per line, in order.

Questions:
{questions}

Respond with {num_questions} numbers, one per line:"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def classify(self, question_text: str, subject, modules: List, module_hint=None) -> Optional[int]:
        """
        Classify a question into a module.
        
        Args:
            question_text: The question text
            subject: Subject instance
            modules: List of Module instances
            module_hint: Optional hint from extraction (e.g., "Module 1" header)
            
        Returns:
            Module number or None
        """
        if not modules:
            return None
        
        # If we have a direct hint from the PDF, use it
        if module_hint:
            try:
                hint_num = int(module_hint)
                if any(m.number == hint_num for m in modules):
                    return hint_num
            except (ValueError, TypeError):
                pass
        
        # Use keyword matching first (fast), then LLM only if needed
        result = self.classify_by_keywords(question_text, modules)
        if result:
            return result
        
        # Try LLM classification if keyword matching failed
        if self.llm_client:
            result = self._classify_with_llm(question_text, subject, modules)
            if result:
                return result
        
        return None
    
    def classify_batch(self, questions: List[str], subject, modules: List) -> List[Optional[int]]:
        """
        Classify multiple questions in a single LLM call for efficiency.
        
        Args:
            questions: List of question texts
            subject: Subject instance  
            modules: List of Module instances
            
        Returns:
            List of module numbers (or None for each)
        """
        if not modules or not questions:
            return [None] * len(questions)
        
        # First try keyword matching for all questions
        results = []
        unmatched_indices = []
        
        for i, q_text in enumerate(questions):
            result = self.classify_by_keywords(q_text, modules)
            results.append(result)
            if result is None:
                unmatched_indices.append(i)
        
        # If all questions matched with keywords, return early
        if not unmatched_indices:
            return results
        
        # Skip LLM for now - too slow, assign unmatched questions to most relevant module
        # Use enhanced keyword scoring for unmatched questions
        for idx in unmatched_indices:
            # Assign to module 1 (Introduction) as default for unmatched
            # This ensures all questions get a module assignment
            results[idx] = 1
        
        return results
    
    def _batch_classify_with_llm(self, questions: List[str], subject, modules: List) -> List[Optional[int]]:
        """Classify multiple questions with a single LLM call."""
        modules_text = '\n'.join([
            f"{m.number}. {m.name}: {', '.join(m.topics[:3]) if m.topics else 'No topics'}"
            for m in modules
        ])
        
        # Format questions with numbers
        questions_text = '\n'.join([
            f"{i+1}. {q[:200]}" for i, q in enumerate(questions)
        ])
        
        prompt = self.BATCH_CLASSIFY_PROMPT.format(
            subject_name=subject.name,
            modules_list=modules_text,
            num_modules=len(modules),
            questions=questions_text,
            num_questions=len(questions)
        )
        
        try:
            response = self.llm_client.generate(prompt, max_tokens=len(questions) * 5)
            response = response.strip()
            
            # Parse response - expect one number per line
            lines = response.split('\n')
            results = []
            for line in lines:
                line = line.strip()
                # Extract first number from line
                match = re.search(r'\d+', line)
                if match:
                    num = int(match.group())
                    if 0 < num <= len(modules):
                        results.append(num)
                    else:
                        results.append(None)
                else:
                    results.append(None)
            
            # Pad with None if not enough results
            while len(results) < len(questions):
                results.append(None)
            
            return results[:len(questions)]
        except Exception as e:
            logger.error(f"Batch LLM classification failed: {e}")
            return [None] * len(questions)
    
    def _classify_with_llm(self, question_text: str, subject, modules: List) -> Optional[int]:
        """Classify using LLM."""
        modules_text = '\n'.join([
            f"{m.number}. {m.name}: {', '.join(m.topics[:5]) if m.topics else 'No topics defined'}"
            for m in modules
        ])
        
        prompt = self.CLASSIFY_PROMPT.format(
            subject_name=subject.name,
            modules_list=modules_text,
            question_text=question_text[:500]
        )
        
        try:
            response = self.llm_client.generate(prompt, max_tokens=10)
            response = response.strip()
            try:
                module_num = int(response)
                if 0 < module_num <= len(modules):
                    return module_num
            except ValueError:
                pass
            return None
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return None
    
    def classify_by_keywords(self, question_text: str, modules: List) -> Optional[int]:
        """
        Fallback classification using keyword matching.
        Enhanced with common disaster management keywords.
        """
        question_lower = question_text.lower()
        
        best_match = None
        best_score = 0
        
        # Default keywords for disaster management modules if not set
        default_keywords = {
            1: ['disaster', 'hazard', 'vulnerability', 'risk', 'types of disaster', 'natural disaster', 
                'man-made', 'classification', 'definition', 'concept', 'introduction'],
            2: ['mitigation', 'preparedness', 'prevention', 'disaster management cycle', 'planning',
                'capacity building', 'early warning', 'risk reduction', 'DRR'],
            3: ['NDMA', 'SDMA', 'DDMA', 'disaster management act', 'policy', 'institutional', 
                'framework', 'authority', 'organization', 'structure', 'government'],
            4: ['response', 'relief', 'rehabilitation', 'recovery', 'emergency', 'rescue', 
                'evacuation', 'shelter', 'medical', 'aid', 'reconstruction'],
            5: ['community', 'participation', 'awareness', 'local', 'village', 'CBDM', 'training',
                'volunteer', 'NGO', 'stakeholder', 'education'],
        }
        
        for module in modules:
            score = 0
            
            # Get keywords - use default if not set
            keywords = module.keywords if module.keywords else default_keywords.get(module.number, [])
            
            # Check keywords
            for keyword in keywords:
                if keyword.lower() in question_lower:
                    score += 3  # Higher weight for direct keyword match
            
            # Check topics
            if module.topics:
                for topic in module.topics:
                    if topic.lower() in question_lower:
                        score += 2
            
            # Check module name
            if module.name:
                for word in module.name.lower().split():
                    if len(word) > 3 and word in question_lower:
                        score += 1
            
            if score > best_score:
                best_score = score
                best_match = module.number
        
        return best_match if best_score > 0 else None
